"""2-sikl yakuniy ko'rigida topilgan holatlar."""
import json
import threading

import httpx
import httpx2
import pytest
from anthropic import DefaultHttpxClient

from engcheck.ai.anthropic_provider import AnthropicProvider
from engcheck.ai.assist import explain_finding
from engcheck.ai.base import AiError
from engcheck.ai.openai_compat import OpenAICompatProvider
from engcheck.ai.registry import Resolution
from engcheck.ai.review import ai_findings
from engcheck.core.auth import create_user
from engcheck.core.models import DocPage, DocType, Finding, FindingStatus, KbChunk, Project, Stage
from engcheck.core.secrets import SecretStore
from engcheck.kb.service import add_source, prompt_text, propose_lesson, reindex, search
from engcheck.review.engine import run_review

from ..review.factories import EQL, PID, make_doc, make_param
from .fakes import FakeProvider

PAGE = "Pump P-101A  discharge has no check valve.\nV-101 PSV set at 20 barg."


@pytest.fixture
def lead(db):
    return create_user(db, "lead", "S3cret-pass", "lead")


@pytest.fixture
def page_doc(db, project):
    d = make_doc(db, project, DocType.OTHER, "GP-NOTE-001")
    db.add(DocPage(document_id=d.id, page_no=1, text=PAGE)); db.flush()
    return d


@pytest.fixture
def rule_finding(db, project):
    a, b = make_doc(db, project, PID, "GP-PID-001"), make_doc(db, project, EQL, "GP-EQL-001")
    make_param(db, project, a, "V-101", "design_pressure", "16 barg", 1600.0)
    make_param(db, project, b, "V-101", "design_pressure", "14 barg", 1400.0)
    run = run_review(db, project.id, None)
    return db.query(Finding).filter_by(run_id=run.id).one()


def _ai_run(db, project, issue, quote="V-101 PSV set at 20 barg"):
    reply = json.dumps([{"quote": quote, "issue": issue, "recommendation": "x", "severity": "minor"}])
    run = run_review(db, project.id, None, resolution=Resolution(FakeProvider(replies=[reply]), "local"))
    return [f for f in db.query(Finding).filter_by(run_id=run.id) if f.source_type == "ai"]


# 1 — AI topilmasi boshqa da'voning qarorini meros olmaydi
def test_ai_finding_never_inherits_confirmation(db, project, page_doc):
    (f,) = _ai_run(db, project, "Birlik ko'rsatilmagan")
    f.status = FindingStatus.confirmed; db.flush()
    (g,) = _ai_run(db, project, "BUTUNLAY BOSHQA DA'VO: idish portlaydi")
    assert g.status == FindingStatus.new and g.actions == []
    (h,) = _ai_run(db, project, "Birlik ko'rsatilmagan")          # aynan o'sha da'vo ham tasdiqni olmaydi
    assert h.status == FindingStatus.new


def test_ai_finding_keeps_rejection_only_for_the_same_claim(db, project, page_doc):
    (f,) = _ai_run(db, project, "Birlik ko'rsatilmagan")
    f.status = FindingStatus.rejected; db.flush()
    assert _ai_run(db, project, "birlik  ko'rsatilmagan")[0].status == FindingStatus.rejected
    assert _ai_run(db, project, "Boshqa da'vo")[0].status == FindingStatus.new


# 2 — dars orqali loyiha matni bulutga chiqmaydi
def test_lesson_text_goes_to_cloud_only_if_its_project_allows(db, settings, lead, project, rule_finding):
    rule_finding.status = FindingStatus.confirmed
    src = propose_lesson(db, settings, rule_finding, lead, "V-101 loyiha bosimi 16 barg; datasheet 14 barg edi.")
    src.approved = True; db.flush()
    assert src.origin_project_id == project.id
    (hit,) = search(db, "loyiha bosimi datasheet")
    assert prompt_text(hit, for_cloud=True) is None and prompt_text(hit, for_cloud=False)
    cloud = FakeProvider(base_url="https://api.example.com", vectors=lambda t: [1.0, 0.0])
    assert reindex(db, cloud) == 0
    project.allow_cloud_ai = True; db.flush()
    (hit,) = search(db, "loyiha bosimi datasheet")
    assert prompt_text(hit, for_cloud=True) and reindex(db, cloud) == 1


def test_lesson_from_project_a_not_in_cloud_prompt_of_project_b(db, settings, lead, project, rule_finding):
    rule_finding.status = FindingStatus.confirmed
    propose_lesson(db, settings, rule_finding, lead, "MAXFIY: V-101 loyiha bosimi design pressure 16 barg").approved = True
    other = Project(name="B", industry="gtl", stage=Stage.DD, allow_cloud_ai=True)
    db.add(other); db.flush()
    p = FakeProvider(base_url="https://api.example.com",
                     replies=[json.dumps({"explanation": "x", "citations": [], "assumptions": []})])
    explain_finding(db, rule_finding, lead, "uz", Resolution(p, "online"))
    assert "MAXFIY" not in p.calls[0][1] and "text withheld" in p.calls[0][1]


# 3 — noto'g'ri AI javobi tekshiruvni yiqitmaydi
@pytest.mark.parametrize("reply", [
    json.dumps([{"quote": "V-101 PSV set at 20 barg", "issue": "x", "severity": ["critical"]}]),
    json.dumps([{"quote": 5, "issue": {"a": 1}}]), json.dumps({"quote": "x"}), "null",
])
def test_malformed_ai_review_reply_keeps_rule_findings(db, project, rule_finding, page_doc, reply):
    run = run_review(db, project.id, None, resolution=Resolution(FakeProvider(replies=[reply] * 5), "local"))
    assert "R001" in [f.rule.code for f in db.query(Finding).filter_by(run_id=run.id)]


def test_unexpected_exception_in_ai_stage_is_recorded_not_raised(db, project, rule_finding, page_doc):
    p = FakeProvider(replies=[RuntimeError("kutilmagan")])
    run = run_review(db, project.id, None, resolution=Resolution(p, "local"))
    assert run.errors == [{"rule": "AI01", "error": "server"}]
    assert [f.rule.code for f in db.query(Finding).filter_by(run_id=run.id)] == ["R001"]


@pytest.mark.parametrize("payload,citations,assumptions", [
    ({"explanation": "Izoh", "citations": 5, "assumptions": "abc"}, [], []),
    ({"explanation": "Izoh [K1]", "citations": None, "assumptions": ["a", 3, ""]}, ["K1"], ["a", "3"]),
])
def test_note_tolerates_wrong_field_types(db, settings, lead, rule_finding, payload, citations, assumptions):
    add_source(db, settings, lead, "Qo'llanma", "literature", text="Design pressure and operating pressure of vessel.")
    note = explain_finding(db, rule_finding, lead, "uz", Resolution(FakeProvider(replies=[json.dumps(payload)]), "local"))
    assert [c["key"] for c in note.citations] == citations and note.assumptions == assumptions


@pytest.mark.parametrize("body", ["<html>captive portal</html>", '{"unexpected": true}', '{"content": "x", "stop_reason": "end_turn"}'])
def test_anthropic_garbage_200_is_a_server_error(body):
    client = DefaultHttpxClient(transport=httpx2.MockTransport(
        lambda r: httpx2.Response(200, content=body.encode(), headers={"content-type": "application/json"})))
    p = AnthropicProvider("c", "claude-opus-5-5", "k", http_client=client)
    with pytest.raises(AiError) as e:
        p.chat("s", "u")
    assert e.value.code == "server"


# 4 — ulanish tekshiruvi tez yiqiladi
def test_anthropic_ping_has_short_timeout_and_no_retries():
    seen = []

    def handler(request):
        seen.append(request.extensions.get("timeout"))
        raise httpx2.ConnectTimeout("tushib qoldi")
    p = AnthropicProvider("c", "claude-opus-5-5", "k", http_client=DefaultHttpxClient(transport=httpx2.MockTransport(handler)))
    with pytest.raises(AiError) as e:
        p.ping()
    assert e.value.code == "unreachable" and len(seen) == 1 and max(seen[0].values()) <= 5.0


# 5, 6 — hech narsa jim tashlanmaydi
def test_truncated_pages_are_counted_and_partial_results_survive_failure(db, project, page_doc):
    d = make_doc(db, project, DocType.OTHER, "GP-NOTE-002")
    db.add(DocPage(document_id=d.id, page_no=1, text="uzun sahifa " * 2000)); db.flush()
    good = json.dumps([{"quote": "V-101 PSV set at 20 barg", "issue": "x", "recommendation": "y", "severity": "minor"}])
    drafts, stats, error = ai_findings(db, project.id, FakeProvider(replies=[good, AiError("unreachable")]), "uz")
    assert len(drafts) == 1 and error == "unreachable"
    assert stats["pages_reviewed"] == 1 and stats["pages_truncated"] == 0
    _, stats, error = ai_findings(db, project.id, FakeProvider(replies=["[]", "[]"]), "uz")
    assert error is None and stats["pages_truncated"] == 1 and stats["pages_reviewed"] == 2


def test_run_keeps_partial_ai_findings_and_stats_when_provider_dies(db, project, page_doc):
    d = make_doc(db, project, DocType.OTHER, "GP-NOTE-002")
    db.add(DocPage(document_id=d.id, page_no=1, text="second page text here")); db.flush()
    good = json.dumps([{"quote": "V-101 PSV set at 20 barg", "issue": "x", "recommendation": "y", "severity": "minor"}])
    run = run_review(db, project.id, None, resolution=Resolution(FakeProvider(replies=[good, AiError("rate_limit")]), "online"))
    assert run.errors == [{"rule": "AI01", "error": "rate_limit"}] and run.ai_stats["pages_reviewed"] == 1
    assert [f.source_type for f in db.query(Finding).filter_by(run_id=run.id)] == ["ai"]


# 7 — iqtibos hujjatdagi asl ko'rinishida saqlanadi
def test_quote_is_stored_as_it_appears_in_the_document(db, project, page_doc):
    reply = json.dumps([{"quote": "pump p-101a discharge HAS NO check valve", "issue": "x", "recommendation": "y"},
                        {"quote": "at 20 ba", "issue": "juda mayda iqtibos", "recommendation": "y"}])
    drafts, stats, _ = ai_findings(db, project.id, FakeProvider(replies=[reply]), "uz")
    assert [d.evidence[0].value for d in drafts] == ["Pump P-101A  discharge has no check valve"]
    assert drafts[0].args["quote"] == "Pump P-101A  discharge has no check valve" and stats["rejected"] == 1


# 11 — kalitlar fayli bir vaqtda yozilganda buzilmaydi
def test_secret_store_concurrent_writes_keep_all_keys(tmp_path):
    store = SecretStore(tmp_path, use_keyring=False)
    threads = [threading.Thread(target=store.set, args=(f"k{i}", f"v{i}")) for i in range(20)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert all(store.get(f"k{i}") == f"v{i}" for i in range(20))
    assert sorted(p.name for p in tmp_path.iterdir()) == ["secret.key", "secrets.enc"]   # vaqtinchalik fayl qolmaydi


# 12 — lokal provayder proksi orqali chiqmaydi va yo'naltirishga ergashmaydi
def test_local_http_provider_ignores_env_proxy_and_never_follows_redirects(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:3128"); monkeypatch.setenv("HTTP_PROXY", "http://proxy.example:3128")
    local = OpenAICompatProvider("l", "http://127.0.0.1:1234/v1", "m")
    cloud = OpenAICompatProvider("c", "https://api.example.com/v1", "m")
    assert local._http.trust_env is False and cloud._http.trust_env is True
    assert local._http.follow_redirects is False and cloud._http.follow_redirects is False
    hops = []

    def handler(r):
        hops.append(str(r.url))
        return httpx.Response(307, headers={"location": "https://evil.example/v1/chat/completions"})
    p = OpenAICompatProvider("l", "http://127.0.0.1:1234/v1", "m", transport=httpx.MockTransport(handler))
    with pytest.raises(AiError):
        p.chat("s", "maxfiy")
    assert hops == ["http://127.0.0.1:1234/v1/chat/completions"]


def test_anthropic_client_does_not_follow_redirects():
    assert AnthropicProvider("c", None, "k")._client._client.follow_redirects is False
