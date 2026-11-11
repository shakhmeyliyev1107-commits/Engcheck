def _confirm(c, pid):
    fid = next(f["id"] for f in c.get(f"/api/projects/{pid}/findings").json() if f["rule"] == "R004")
    c.post(f"/api/findings/{fid}/actions", json={"action": "confirm", "comment": "tuzatilsin"})


def test_export_import_roundtrip_over_api(client_as, reviewed):
    c, pid = reviewed
    _confirm(c, pid)
    lead = client_as("lead")
    assert c.post(f"/api/projects/{pid}/export", json={}).status_code == 403          # muhandis eksport qila olmaydi
    r = lead.post(f"/api/projects/{pid}/export", json={"passphrase": "parol-123"})
    assert r.status_code == 200 and r.headers["content-disposition"].endswith('.engpkg"') and not r.content.startswith(b"PK")
    bad = c.post("/api/projects/import", files={"file": ("p.engpkg", r.content)}, data={"passphrase": "xato"})
    assert bad.status_code == 422 and bad.json()["code"] == "pkg_wrong_passphrase"
    assert c.post("/api/projects/import", files={"file": ("p.engpkg", r.content)}).json()["code"] == "pkg_passphrase_required"
    ok = c.post("/api/projects/import", files={"file": ("p.engpkg", r.content)}, data={"passphrase": "parol-123"})
    assert ok.status_code == 201
    body = ok.json()
    assert (body["documents"], body["decisions_restored"], body["decisions_unmatched"]) == (6, 1, 0)
    new = body["project"]["id"]
    assert new != pid and body["project"]["allow_cloud_ai"] is False
    items = c.get(f"/api/projects/{new}/findings").json()
    assert len(items) == 8 and [f["status"] for f in items if f["rule"] == "R004"] == ["confirmed"]
    detail = c.get(f"/api/findings/{next(f['id'] for f in items if f['rule'] == 'R004')}").json()
    assert detail["actions"][0]["action"] == "imported" and detail["actions"][0]["comment"] == "engineer: tuzatilsin"
    assert len(c.get("/api/projects").json()) == 2


def test_failed_import_leaves_nothing_behind(client_as, reviewed, settings):
    c, pid = reviewed
    before = sorted(p.name for p in (settings.data_dir / "files").iterdir())
    r = c.post("/api/projects/import", files={"file": ("x.engpkg", b"bu paket emas")})
    assert r.status_code == 422 and r.json()["code"] == "pkg_invalid_package"
    assert client_as("viewer").post("/api/projects/import", files={"file": ("x.engpkg", b"x")}).status_code == 403
    assert len(c.get("/api/projects").json()) == 1
    assert sorted(p.name for p in (settings.data_dir / "files").iterdir()) == before
