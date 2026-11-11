from generate_sample_project import plot_plan


def test_layout3d_flow_with_sample_plot_plan(client_as, reviewed, upload, tmp_path):
    c, pid = reviewed
    viewer = client_as("viewer")
    assert c.get(f"/api/projects/{pid}/layout3d").json()["exists"] is False
    assert c.post(f"/api/projects/{pid}/layout3d/edits", json={"op": "move", "id": "eq:V-101", "x": 1, "y": 1}).json()["code"] == "layout3d_no_layout"
    assert viewer.post(f"/api/projects/{pid}/layout3d/generate").status_code == 403
    m = c.post(f"/api/projects/{pid}/layout3d/generate").json()
    assert m["plot_plan"] is None and {i["position_source"] for i in m["items"]} == {"assumed"} and len(m["items"]) == 6

    assert upload(c, pid, plot_plan(tmp_path / "GP-PLT-001_RevA.dxf")).json()["parse_status"] == "parsed"
    assert c.get(f"/api/projects/{pid}/layout3d").json()["stale"] is True
    m = c.post(f"/api/projects/{pid}/layout3d/generate").json()
    items = {i["id"]: i for i in m["items"]}
    assert m["plot_plan"] == "GP-PLT-001" and m["unit_assumed"] == "mm"
    assert (items["eq:V-102"]["x"], items["eq:V-102"]["y"], items["eq:V-102"]["position_source"]) == (12.0, 12.0, "document")
    assert items["eq:E-102"]["position_source"] == "assumed"            # bosh rejada yo'q
    assert len(c.get(f"/api/projects/{pid}/findings").json()) == 8      # bosh reja tekshiruv natijasini o'zgartirmaydi

    assert viewer.post(f"/api/projects/{pid}/layout3d/edits", json={"op": "rotate", "id": "eq:E-101", "rot": 90}).status_code == 403
    r = c.post(f"/api/projects/{pid}/layout3d/edits", json={"op": "move", "id": "eq:V-102", "x": 15, "y": 12})
    assert r.status_code == 201 and r.json()["differences"] == [{"kind": "position_changed", "label": "V-102"}]
    assert c.post(f"/api/projects/{pid}/layout3d/edits", json={"op": "resize", "id": "eq:V-101", "w": 0, "d": 1, "h": 1}).json()["code"] == "layout3d_invalid_op"
    assert c.post(f"/api/projects/{pid}/layout3d/edits", json={"op": "rotate", "id": "eq:YOQ", "rot": 5}).json()["code"] == "layout3d_not_applicable"
    assert c.post(f"/api/projects/{pid}/layout3d/undo").json()["differences"] == []
    assert c.post(f"/api/projects/{pid}/layout3d/redo").json()["can_undo"] is True
    assert c.post(f"/api/projects/{pid}/layout3d/redo").json()["code"] == "layout3d_nothing_to_redo"
    dash = c.get(f"/api/projects/{pid}/dashboard").json()["layout3d"]
    assert dash == {"exists": True, "stale": False, "items": 6, "differences": 1}
    assert c.get("/api/projects/9999/layout3d").status_code == 404
