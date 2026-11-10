def _findings(c, pid, **params):
    return c.get(f"/api/projects/{pid}/findings", params=params).json()


def _find(c, pid, rule, tag):
    return next(f for f in _findings(c, pid) if f["rule"] == rule and f["tag"] == tag)


def test_review_yields_eight_findings_with_required_fields(reviewed):
    c, pid = reviewed
    items = _findings(c, pid)
    assert len(items) == 8
    f = _find(c, pid, "R001", "V-101")
    assert f["severity"] == "critical" and f["status"] == "new" and f["confidence"] == "high"
    assert f["source_type"] == "rule" and "V-101" in f["description"]
    detail = c.get(f"/api/findings/{f['id']}").json()
    for key in ("description", "rationale", "recommendation", "source", "severity", "status", "confidence"):
        assert detail[key], key
    assert detail["source"] == "Loyiha hujjatlari o‘rtasidagi ichki nomuvofiqlik"
    assert len(detail["evidence"]) == 3 and detail["project_id"] == pid
    e = detail["evidence"][0]
    assert {"document_id", "doc_number", "filename", "page_no", "location", "value"} <= set(e)


def test_findings_localized_per_user(reviewed):
    c, pid = reviewed
    c.patch("/api/auth/me", json={"locale": "en"})
    f = _find(c, pid, "R001", "V-101")
    assert f["description"] == "V-101: design pressure differs between documents"
    assert f["rule_title"] == "Parameter differs between documents"


def test_findings_filters(reviewed):
    c, pid = reviewed
    assert len(_findings(c, pid, severity="critical")) == 2
    assert len(_findings(c, pid, rule="R002")) == 2
    assert [f["tag"] for f in _findings(c, pid, tag="P-101B")] == ["P-101B"]
    docs = {d["doc_number"]: d["id"] for d in c.get(f"/api/projects/{pid}/documents").json()}
    assert {f["rule"] for f in _findings(c, pid, document_id=docs["GP-MS-001"])} == set()
    assert {(f["rule"], f["tag"]) for f in _findings(c, pid, document_id=docs["GP-DS-V101"])} == {
        ("R001", "V-101"), ("R006", None)}
    assert _findings(c, pid, status="confirmed") == []
    assert len(_findings(c, pid, status="open")) == 8


def test_decision_flow_and_audit(reviewed, client_as):
    c, pid = reviewed
    fid = _find(c, pid, "R001", "V-101")["id"]
    r = c.post(f"/api/findings/{fid}/actions", json={"action": "confirm", "comment": "datasheet xato"})
    assert r.status_code == 200 and r.json()["status"] == "confirmed"
    hist = r.json()["actions"]
    assert [(a["action"], a["comment"], a["user"]) for a in hist] == [("confirm", "datasheet xato", "engineer")]
    assert c.post(f"/api/findings/{fid}/actions", json={"action": "mark_fixed", "comment": ""}).json()["status"] == "fixed"
    audit = client_as("admin").get("/api/audit").json()
    assert [a["action"] for a in audit if a["object_type"] == "finding"] == ["finding.mark_fixed", "finding.confirm"]
    assert client_as("admin").get("/api/audit/verify").json() == {"ok": True, "broken_at": None}


def test_invalid_transition_409(reviewed):
    c, pid = reviewed
    fid = _findings(c, pid)[0]["id"]
    r = c.post(f"/api/findings/{fid}/actions", json={"action": "mark_fixed", "comment": ""})
    assert r.status_code == 409 and r.json()["code"] == "invalid_transition"
    assert c.get(f"/api/findings/{fid}").json()["status"] == "new"


def test_reject_requires_comment(reviewed):
    c, pid = reviewed
    fid = _findings(c, pid)[0]["id"]
    r = c.post(f"/api/findings/{fid}/actions", json={"action": "reject", "comment": "  "})
    assert r.status_code == 422 and r.json()["code"] == "comment_required"
    assert c.post(f"/api/findings/{fid}/actions", json={"action": "reject", "comment": "ataylab"}).json()["status"] == "rejected"


def test_unknown_action_422(reviewed):
    c, pid = reviewed
    fid = _findings(c, pid)[0]["id"]
    assert c.post(f"/api/findings/{fid}/actions", json={"action": "apply_to_document", "comment": ""}).status_code == 422


def test_rerun_keeps_decision(reviewed):
    c, pid = reviewed
    fid = _find(c, pid, "R003", "P-101B")["id"]
    c.post(f"/api/findings/{fid}/actions", json={"action": "reject", "comment": "vendor keyin beradi"})
    c.post(f"/api/projects/{pid}/reviews")
    f = _find(c, pid, "R003", "P-101B")
    assert f["id"] != fid and f["status"] == "rejected"
    assert len(_findings(c, pid)) == 8


def test_dashboard_counts(reviewed):
    c, pid = reviewed
    fid = _find(c, pid, "R004", "V-102")["id"]
    c.post(f"/api/findings/{fid}/actions", json={"action": "confirm", "comment": ""})
    d = c.get(f"/api/projects/{pid}/dashboard").json()
    assert d["documents"]["total"] == 6 and d["documents"]["by_type"]["DATASHEET"] == 2
    assert d["documents"]["by_status"] == {"parsed": 6}
    assert d["findings"]["total"] == 8
    assert d["findings"]["by_severity"] == {"critical": 2, "major": 4, "minor": 2, "info": 0}
    assert d["findings"]["by_status"]["new"] == 7 and d["findings"]["by_status"]["confirmed"] == 1
    assert d["findings"]["open"] == 7 and d["findings"]["open_critical"] == 1
    assert d["findings"]["confirmed_unfixed"] == 1
    assert d["last_run"]["ai_mode"] == "none" and d["last_run"]["errors"] == []
    assert d["rules"] == {"enabled": 7, "total": 7}


def test_dashboard_before_any_review(client_as):
    c = client_as("engineer")
    pid = c.post("/api/projects", json={"name": "GP", "industry": "gtl", "stage": "FEED"}).json()["id"]
    d = c.get(f"/api/projects/{pid}/dashboard").json()
    assert d["last_run"] is None and d["findings"]["total"] == 0 and d["documents"]["total"] == 0


def test_disabling_rule_removes_its_findings_on_next_run(reviewed, client_as):
    c, pid = reviewed
    client_as("lead").patch("/api/rules/R002", json={"enabled": False})
    c.post(f"/api/projects/{pid}/reviews")
    assert {f["rule"] for f in _findings(c, pid)} == {"R001", "R003", "R004", "R005", "R006"}
    rules = {r["code"]: r for r in c.get("/api/rules").json()}
    assert rules["R002"]["enabled"] is False and rules["R002"]["title"]


def test_finding_of_missing_id_404(client_as):
    assert client_as("viewer").get("/api/findings/12345").status_code == 404


def test_findings_filter_by_document_type(reviewed):
    c, pid = reviewed
    assert {(f["rule"], f["tag"]) for f in _findings(c, pid, doc_type="MATERIAL_SPEC")} == set()
    assert {f["rule"] for f in _findings(c, pid, doc_type="LINE_LIST")} == {"R002", "R005"}
    assert c.get(f"/api/projects/{pid}/findings", params={"doc_type": "NOPE"}).status_code == 422


def test_document_list_marks_superseded_revision(client_as, sample_docs, upload, tmp_path):
    import openpyxl
    c = client_as("engineer")
    pid = c.post("/api/projects", json={"name": "GP", "industry": "gtl", "stage": "DD"}).json()["id"]
    upload(c, pid, sample_docs[1])                                   # GP-EQL-001 Rev B
    newer = tmp_path / "GP-EQL-001_RevC.xlsx"
    wb = openpyxl.Workbook(); wb.active.append(["Tag No.", "Material"]); wb.active.append(["V-101", "CS"]); wb.save(newer)
    with open(newer, "rb") as f:
        c.post(f"/api/projects/{pid}/documents", files={"file": (newer.name, f)},
               data={"doc_type": "EQUIPMENT_LIST", "discipline": "mechanical", "doc_number": "GP-EQL-001", "revision": "C"})
    assert {d["revision"]: d["superseded"] for d in c.get(f"/api/projects/{pid}/documents").json()} == {"B": True, "C": False}
