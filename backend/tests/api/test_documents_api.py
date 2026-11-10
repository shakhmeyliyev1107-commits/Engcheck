def _project(c):
    return c.post("/api/projects", json={"name": "GP", "industry": "gas_processing", "stage": "DD"}).json()["id"]


def test_project_validation(client_as):
    c = client_as("engineer")
    r = c.post("/api/projects", json={"name": "", "industry": "gtl", "stage": "FEED"})
    assert r.status_code == 422 and r.json()["code"] == "validation_error"
    assert c.post("/api/projects", json={"name": "x", "industry": "gtl", "stage": "LATER"}).status_code == 422
    assert c.post("/api/projects", json={"name": "x", "industry": "bakery", "stage": "DD"}).status_code == 422


def test_upload_returns_parsed_document(client_as, sample_docs, upload):
    c = client_as("engineer")
    pid = _project(c)
    r = upload(c, pid, sample_docs[1])
    assert r.status_code == 201
    body = r.json()
    assert body["parse_status"] == "parsed" and body["doc_number"] == "GP-EQL-001" and body["revision"] == "B"
    assert [d["id"] for d in c.get(f"/api/projects/{pid}/documents").json()] == [body["id"]]


def test_document_detail_has_pages_params_and_unmapped(client_as, sample_docs, upload):
    c = client_as("engineer")
    pid = _project(c)
    doc = c.get(f"/api/documents/{upload(c, pid, sample_docs[1]).json()['id']}").json()
    assert doc["pages"][0]["page_no"] == 1 and "V-101" in doc["pages"][0]["text"]
    p = next(p for p in doc["params"] if p["tag"] == "V-101" and p["param"] == "design_pressure")
    assert p["raw_value"] == "16" and p["si_value"] == 1600.0 and p["location"] == "Equipment!C5"
    assert p["page_no"] == 1 and p["confidence"] == "high" and p["param_name"] == "loyiha bosimi"
    assert "Description" in doc["unmapped_headers"]


def test_original_file_download_is_byte_identical(client_as, sample_docs, upload):
    c = client_as("engineer")
    pid = _project(c)
    did = upload(c, pid, sample_docs[3]).json()["id"]
    r = c.get(f"/api/documents/{did}/file")
    assert r.status_code == 200 and r.content == sample_docs[3].path.read_bytes()


def test_duplicate_upload_409(client_as, sample_docs, upload):
    c = client_as("engineer")
    pid = _project(c)
    upload(c, pid, sample_docs[0])
    r = upload(c, pid, sample_docs[0])
    assert r.status_code == 409 and r.json()["code"] == "duplicate_document"


def test_dwg_upload_201_with_unsupported_status(client_as, tmp_path):
    c = client_as("engineer")
    pid = _project(c)
    r = c.post(f"/api/projects/{pid}/documents", files={"file": ("plan.dwg", b"AC1032" + b"\0" * 64)},
               data={"doc_type": "PID", "discipline": "process"})
    assert r.status_code == 201
    assert r.json()["parse_status"] == "unsupported"
    assert "DXF" in r.json()["parse_message"]


def test_corrupt_upload_does_not_break_later_uploads(client_as, sample_docs, upload):
    c = client_as("engineer")
    pid = _project(c)
    r = c.post(f"/api/projects/{pid}/documents", files={"file": ("bad.xlsx", b"PK\x03\x04 broken")},
               data={"doc_type": "LINE_LIST", "discipline": "piping"})
    assert r.status_code == 201 and r.json()["parse_status"] == "error"
    assert upload(c, pid, sample_docs[2]).json()["parse_status"] == "parsed"


def test_upload_rejects_bad_doc_type_and_empty_file(client_as):
    c = client_as("engineer")
    pid = _project(c)
    r = c.post(f"/api/projects/{pid}/documents", files={"file": ("a.pdf", b"%PDF-1.4")},
               data={"doc_type": "NOVEL", "discipline": "process"})
    assert r.status_code == 422 and r.json()["code"] == "validation_error"
    r = c.post(f"/api/projects/{pid}/documents", files={"file": ("a.pdf", b"")},
               data={"doc_type": "PFD", "discipline": "process"})
    assert r.status_code == 201 and r.json()["parse_status"] == "error"


def test_upload_to_missing_project_404(client_as):
    r = client_as("engineer").post("/api/projects/999/documents", files={"file": ("a.pdf", b"x")},
                                   data={"doc_type": "PFD", "discipline": "process"})
    assert r.status_code == 404 and r.json()["code"] == "not_found"


def test_filename_with_path_is_sanitised(client_as, settings):
    c = client_as("engineer")
    pid = _project(c)
    r = c.post(f"/api/projects/{pid}/documents", files={"file": ("../../evil.dwg", b"AC1032" + b"\0" * 64)},
               data={"doc_type": "PID", "discipline": "process"})
    assert r.json()["filename"] == "evil.dwg"
    assert not (settings.data_dir.parent / "evil.dwg").exists()


def test_doc_type_suggestion(client_as):
    r = client_as("viewer").get("/api/doc-type-suggestion", params={"filename": "GP-PID-001_RevC.dxf"})
    assert r.json() == {"doc_type": "PID", "doc_number": "GP-PID-001", "revision": "C"}


def test_delete_document(client_as, sample_docs, upload):
    c = client_as("engineer")
    pid = _project(c)
    did = upload(c, pid, sample_docs[0]).json()["id"]
    assert c.delete(f"/api/documents/{did}").status_code == 204
    assert c.get(f"/api/documents/{did}").status_code == 404
    assert upload(c, pid, sample_docs[0]).status_code == 201   # qayta yuklash mumkin
