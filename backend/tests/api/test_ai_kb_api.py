import json

import pytest

from tests.ai.fakes import FakeProvider

KEY = "sk-test-SECRET-9f3a"
GUIDE = "Design pressure shall not be less than the maximum operating pressure of the vessel."


@pytest.fixture
def fake_ai(app):
    """Provayder fabrikasini soxtasiga almashtiradi; javoblar provayder nomi bo'yicha."""
    state = {"replies": {}, "fail": {}, "built": {}}

    def factory(row, key):
        p = FakeProvider(row.name, row.base_url, replies=state["replies"].get(row.name), fail=state["fail"].get(row.name))
        state["built"][row.name] = (p, key)
        return p
    app.state.provider_factory = factory
    return state


def _provider(c, **kw):
    body = {"name": "lokal", "kind": "ollama", "base_url": "http://127.0.0.1:11434", "model": "llama3"}
    body.update(kw)
    return c.post("/api/ai/providers", json=body)


def test_provider_crud_and_key_never_leaves_the_store(client_as, settings, fake_ai):
    a = client_as("admin")
    r = _provider(a, name="bulut", kind="openai_compatible", base_url="https://api.example.com/v1", model="gpt-x", api_key=KEY)
    assert r.status_code == 201
    body = r.json()
    assert body["has_key"] is True and body["is_local"] is False and "api_key" not in body
    pid = body["id"]
    assert a.post(f"/api/ai/providers/{pid}/test").json() == {"ok": True, "error": None, "message": None}
    assert fake_ai["built"]["bulut"][1] == KEY                       # kalit provayderga yetib boradi
    everything = json.dumps([a.get("/api/ai/providers").json(), a.get("/api/audit").json()])
    assert KEY not in everything
    assert KEY.encode() not in (settings.data_dir / "engcheck.db").read_bytes()
    r = a.patch(f"/api/ai/providers/{pid}", json={"model": "gpt-y", "clear_key": True})
    assert r.json()["model"] == "gpt-y" and r.json()["has_key"] is False
    assert a.delete(f"/api/ai/providers/{pid}").status_code == 204 and a.get("/api/ai/providers").json() == []
    actions = [x["action"] for x in a.get("/api/audit").json()]
    assert {"ai_provider.create", "ai_provider.update", "ai_provider.delete"} <= set(actions)


def test_provider_validation_and_permissions(client_as, fake_ai):
    a, lead = client_as("admin"), client_as("lead")
    assert _provider(lead).status_code == 403
    assert _provider(a, kind="telepathy").status_code == 422
    assert _provider(a, kind="openai_compatible", base_url=None).json()["code"] == "base_url_required"
    assert _provider(a, base_url="ftp://x").json()["code"] == "base_url_invalid"
    assert _provider(a).status_code == 201
    assert _provider(a).json()["code"] == "name_taken"
    r = _provider(a, name="claude", kind="anthropic", base_url=None, model=None, api_key=KEY)
    assert r.json()["model"] == "claude-opus-5-5" and r.json()["is_local"] is False
    assert [p["name"] for p in lead.get("/api/ai/providers").json()] == ["lokal", "claude"]   # ko'rish hammaga


def test_default_switching_and_failed_test_message(client_as, fake_ai):
    a = client_as("admin")
    one, two = _provider(a).json()["id"], _provider(a, name="ikkinchi").json()["id"]
    a.post(f"/api/ai/providers/{two}/default")
    assert {p["name"]: p["is_default"] for p in a.get("/api/ai/providers").json()} == {"lokal": False, "ikkinchi": True}
    a.post(f"/api/ai/providers/{one}/default")
    assert {p["name"]: p["is_default"] for p in a.get("/api/ai/providers").json()} == {"lokal": True, "ikkinchi": False}
    fake_ai["fail"]["lokal"] = "auth"
    r = a.post(f"/api/ai/providers/{one}/test").json()
    assert r["ok"] is False and r["error"] == "auth" and r["message"] == "API kaliti noto‘g‘ri yoki ruxsat yo‘q"


def test_ai_status_and_cloud_consent(client_as, reviewed, fake_ai):
    c, pid = reviewed
    a, lead = client_as("admin"), client_as("lead")
    s = c.get(f"/api/projects/{pid}/ai-status").json()
    assert (s["mode"], s["reason"], s["allow_cloud_ai"]) == ("none", "no_provider", False)
    _provider(a, name="bulut", kind="openai_compatible", base_url="https://api.example.com/v1", model="m", api_key=KEY)
    s = c.get(f"/api/projects/{pid}/ai-status").json()
    assert s["reason"] == "cloud_not_allowed" and "bulutli" in s["message"]
    assert c.patch(f"/api/projects/{pid}", json={"allow_cloud_ai": True}).status_code == 403   # muhandis ruxsat bera olmaydi
    assert lead.patch(f"/api/projects/{pid}", json={"allow_cloud_ai": True}).json()["allow_cloud_ai"] is True
    s = c.get(f"/api/projects/{pid}/ai-status").json()
    assert (s["mode"], s["provider"], s["reason"]) == ("online", "bulut", None)
    fake_ai["fail"]["bulut"] = "unreachable"                           # internet yo'q
    assert c.get(f"/api/projects/{pid}/ai-status").json()["reason"] == "unreachable"
    _provider(a)                                                       # lokal model qo'shildi
    s = c.get(f"/api/projects/{pid}/ai-status").json()
    assert (s["mode"], s["provider"]) == ("local", "lokal")
    assert "project.update" in [x["action"] for x in a.get("/api/audit").json()]


def test_kb_upload_search_approve_flow(client_as, tmp_path):
    eng, lead, viewer = client_as("engineer"), client_as("lead"), client_as("viewer")
    r = eng.post("/api/kb/sources", data={"title": "Idish qo'llanmasi", "kind": "literature", "text": GUIDE})
    assert r.status_code == 201 and r.json()["approved"] is False and r.json()["chunks"] == 1
    sid = r.json()["id"]
    assert viewer.get("/api/kb/search", params={"q": "design pressure"}).json() == []
    assert eng.patch(f"/api/kb/sources/{sid}", json={"approved": True}).status_code == 403
    assert lead.patch(f"/api/kb/sources/{sid}", json={"approved": True, "edition": "2024"}).json()["approved"] is True
    (hit,) = viewer.get("/api/kb/search", params={"q": "design pressure"}).json()
    assert hit["title"] == "Idish qo'llanmasi" and hit["edition"] == "2024" and "text" not in hit
    f = tmp_path / "note.txt"; f.write_text("Amine service requires post weld heat treatment of carbon steel.")
    with open(f, "rb") as fh:
        r = lead.post("/api/kb/sources", files={"file": ("note.txt", fh)}, data={"title": "PWHT", "kind": "note"})
    assert r.status_code == 201 and r.json()["approved"] is True
    with open(f, "rb") as fh:
        assert lead.post("/api/kb/sources", files={"file": ("note.txt", fh)},
                         data={"title": "PWHT2", "kind": "note"}).json()["code"] == "kb_duplicate"
    assert viewer.post("/api/kb/sources", data={"title": "x", "kind": "note", "text": "abc def"}).status_code == 403
    assert eng.post("/api/kb/sources", data={"title": "x", "kind": "note"}).json()["code"] == "kb_empty"
    assert eng.post("/api/kb/sources", data={"title": "x", "kind": "poem", "text": "a b"}).status_code == 422
    assert lead.delete(f"/api/kb/sources/{sid}").status_code == 204
    assert [s["title"] for s in viewer.get("/api/kb/sources").json()] == ["PWHT"]


def test_licensed_source_is_never_returned_in_full(client_as):
    lead = client_as("lead")
    text = "Clause 5.1 design pressure requirement. " + "Licensed body text. " * 60
    sid = lead.post("/api/kb/sources", data={"title": "ASME VIII", "kind": "standard", "text": text,
                                             "standard_code": "ASME BPVC VIII-1", "edition": "2023",
                                             "license_type": "licensed"}).json()["id"]
    (hit,) = lead.get("/api/kb/search", params={"q": "design pressure requirement"}).json()
    assert len(hit["excerpt"]) <= 300 and hit["license_type"] == "licensed"
    assert lead.get(f"/api/kb/sources/{sid}/file").status_code == 404        # yuklab olish yo'li yo'q
    lead.patch(f"/api/kb/sources/{sid}", json={"status": "withdrawn"})
    assert lead.get("/api/kb/search", params={"q": "design pressure requirement"}).json() == []


def test_ai_note_flow(client_as, reviewed, fake_ai):
    c, pid = reviewed
    a, lead = client_as("admin"), client_as("lead")
    fid = next(f["id"] for f in c.get(f"/api/projects/{pid}/findings").json() if f["rule"] == "R004")
    r = c.post(f"/api/findings/{fid}/ai-notes")
    assert r.status_code == 503 and r.json()["code"] == "ai_unavailable" and "provayder" in r.json()["message"]
    _provider(a)
    lead.post("/api/kb/sources", data={"title": "Idish qo'llanmasi", "kind": "literature", "text": GUIDE})
    fake_ai["replies"]["lokal"] = [json.dumps({"explanation": "Loyiha bosimi ish bosimidan past [K1].",
                                               "citations": ["K1", "K9"], "assumptions": ["Qiymatlar almashib qolgan bo'lishi mumkin"]})]
    r = c.post(f"/api/findings/{fid}/ai-notes")
    assert r.status_code == 201
    note = r.json()
    assert note["status"] == "proposed" and note["ai_mode"] == "local" and note["provider"] == "lokal"
    assert [x["key"] for x in note["citations"]] == ["K1"] and note["citations"][0]["title"] == "Idish qo'llanmasi"
    detail = c.get(f"/api/findings/{fid}").json()
    assert detail["status"] == "new" and [n["id"] for n in detail["ai_notes"]] == [note["id"]]
    assert client_as("viewer").post(f"/api/findings/{fid}/ai-notes").status_code == 403
    r = c.post(f"/api/ai-notes/{note['id']}/decision", json={"decision": "accepted"})
    assert r.json()["status"] == "accepted" and r.json()["decided_by"] == "engineer"
    assert c.post(f"/api/ai-notes/{note['id']}/decision", json={"decision": "maybe"}).status_code == 422
    fake_ai["replies"]["lokal"] = ["bu JSON emas"]
    r = c.post(f"/api/findings/{fid}/ai-notes")
    assert r.status_code == 502 and r.json()["code"] == "ai_bad_response"
    assert "ai_note.accepted" in [x["action"] for x in a.get("/api/audit").json()]


def test_review_with_ai_and_dashboard(client_as, reviewed, fake_ai):
    c, pid = reviewed
    r = c.post(f"/api/projects/{pid}/reviews", json={"use_ai": True}).json()
    assert (r["ai_mode"], r["ai_note"]) == ("none", "no_provider") and "provayder" in r["ai_message"]
    _provider(client_as("admin"))
    quote = "Ref. P&ID GP-PID-001 Rev A"
    fake_ai["replies"]["lokal"] = [json.dumps([{"quote": quote, "issue": "Havola eskirgan bo'lishi mumkin",
                                                "recommendation": "Tekshiring", "severity": "minor"}])] * 20   # har sahifaga bir xil javob: iqtibos faqat bittasida bor
    r = c.post(f"/api/projects/{pid}/reviews", json={"use_ai": True}).json()
    assert (r["ai_mode"], r["ai_provider"]) == ("local", "lokal") and r["ai_stats"]["pages_reviewed"] >= 6
    items = c.get(f"/api/projects/{pid}/findings").json()
    ai = [f for f in items if f["source_type"] == "ai"]
    assert len(items) == 9 and len(ai) == 1 and ai[0]["confidence"] == "low" and ai[0]["rule"] == "AI01"
    detail = c.get(f"/api/findings/{ai[0]['id']}").json()
    assert "AI xulosasi" in detail["source"] and quote in detail["rationale"]
    d = c.get(f"/api/projects/{pid}/dashboard").json()
    assert d["last_run"]["ai_mode"] == "local" and d["last_run"]["ai_provider"] == "lokal"
    assert d["findings"]["ai"] == 1 and d["kb"] == {"sources": 0, "pending": 0}
    plain = c.post(f"/api/projects/{pid}/reviews").json()                 # AI so'ralmasa ishlatilmaydi
    assert plain["ai_mode"] == "none" and plain["ai_note"] is None
    assert len(c.get(f"/api/projects/{pid}/findings").json()) == 8


def test_lesson_flow(client_as, reviewed):
    c, pid = reviewed
    lead = client_as("lead")
    fid = next(f["id"] for f in c.get(f"/api/projects/{pid}/findings").json() if f["rule"] == "R006")
    assert c.post(f"/api/findings/{fid}/lesson", json={}).json()["code"] == "lesson_not_allowed"
    c.post(f"/api/findings/{fid}/actions", json={"action": "confirm", "comment": "datasheet yangilanmagan"})
    r = c.post(f"/api/findings/{fid}/lesson", json={"text": "Datasheet chiqarishdan oldin P&ID reviziyasini solishtiring."})
    assert r.status_code == 201 and r.json()["kind"] == "lesson" and r.json()["approved"] is False
    assert c.get("/api/kb/search", params={"q": "reviziyasini solishtiring"}).json() == []
    lead.patch(f"/api/kb/sources/{r.json()['id']}", json={"approved": True})
    assert c.get("/api/kb/search", params={"q": "reviziyasini solishtiring"}).json()[0]["kind"] == "lesson"
    assert c.get(f"/api/projects/{pid}/dashboard").json()["kb"] == {"sources": 1, "pending": 0}


def test_reindex_reports_when_embeddings_unavailable(client_as, fake_ai):
    lead = client_as("lead")
    assert lead.post("/api/kb/reindex", json={}).json()["code"] == "ai_unavailable"
    _provider(client_as("admin"))
    assert lead.post("/api/kb/reindex", json={}).json()["code"] == "embeddings_unsupported"
    assert client_as("engineer").post("/api/kb/reindex", json={}).status_code == 403
