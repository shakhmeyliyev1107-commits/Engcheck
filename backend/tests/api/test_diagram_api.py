def test_diagram_flow_over_api_with_sample_project(client_as, reviewed):
    c, pid = reviewed
    viewer = client_as("viewer")
    assert c.get(f"/api/projects/{pid}/diagram").json()["exists"] is False
    assert c.post(f"/api/projects/{pid}/diagram/undo").json()["code"] == "diagram_nothing_to_undo"
    assert c.post(f"/api/projects/{pid}/diagram/edits", json={"op": "move", "id": "eq:V-101", "x": 1, "y": 1}).json()["code"] == "diagram_no_diagram"
    assert viewer.post(f"/api/projects/{pid}/diagram/generate").status_code == 403
    d = c.post(f"/api/projects/{pid}/diagram/generate").json()
    ids = {n["id"] for n in d["nodes"]}
    assert {"eq:V-101", "eq:V-102", "eq:P-101A", "eq:P-101B", "eq:E-101", "eq:E-102", "bd:B.L.", "bd:Drain"} == ids
    edges = {e["label"]: (e["from"], e["to"], e["source"]) for e in d["edges"]}
    assert edges['6"-AM-1003-B1A'] == ("eq:V-101", "eq:V-102", "document") and len(edges) == 5 and d["unconnected"] == []
    assert viewer.post(f"/api/projects/{pid}/diagram/edits", json={"op": "move", "id": "eq:V-101", "x": 1, "y": 1}).status_code == 403
    r = c.post(f"/api/projects/{pid}/diagram/edits", json={"op": "add_node", "id": "m:a", "label": "V-103", "kind": "vessel", "x": 5, "y": 6})
    assert r.status_code == 201 and r.json()["differences"] == [{"kind": "node_added", "label": "V-103"}]
    assert c.post(f"/api/projects/{pid}/diagram/edits", json={"op": "boom"}).json()["code"] == "diagram_invalid_op"
    assert c.post(f"/api/projects/{pid}/diagram/edits", json={"op": "move", "id": "eq:YOQ", "x": 1, "y": 1}).json()["code"] == "diagram_not_applicable"
    assert c.post(f"/api/projects/{pid}/diagram/undo").json()["differences"] == []
    assert c.post(f"/api/projects/{pid}/diagram/redo").json()["can_undo"] is True
    svg = viewer.get(f"/api/projects/{pid}/diagram.svg")
    assert svg.status_code == 200 and svg.headers["content-type"].startswith("image/svg+xml") and "V-103" in svg.text
    dash = c.get(f"/api/projects/{pid}/dashboard").json()["diagram"]
    assert dash == {"exists": True, "stale": False, "nodes": 9, "differences": 1}
    assert len(c.get(f"/api/projects/{pid}/findings").json()) == 8        # From/To ustunlari topilmalarga ta'sir qilmadi


def test_diagram_goes_stale_when_documents_change(client_as, reviewed):
    c, pid = reviewed
    c.post(f"/api/projects/{pid}/diagram/generate")
    doc = next(d for d in c.get(f"/api/projects/{pid}/documents").json() if d["doc_number"] == "GP-LL-001")
    c.delete(f"/api/documents/{doc['id']}")
    d = c.get(f"/api/projects/{pid}/diagram").json()
    assert d["stale"] is True
    d = c.post(f"/api/projects/{pid}/diagram/generate").json()
    assert d["stale"] is False and all(e["source"] == "inferred" for e in d["edges"])   # endi faqat chizmadagi yaqinlik
