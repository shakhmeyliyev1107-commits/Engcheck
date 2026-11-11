import os

import pytest

from generate_sample_project import generate


@pytest.fixture
def folder(tmp_path):
    root = tmp_path / "loyiha hujjatlari"
    generate(root / "process")
    (root / "process" / "~$lock.docx").write_bytes(b"x")          # Office vaqtinchalik fayli
    (root / "eski.dwg").write_bytes(b"AC1027")
    (root / "izoh.txt").write_text("salom")
    (root / ".git").mkdir(); (root / ".git" / "x.pdf").write_bytes(b"%PDF")
    return root


@pytest.fixture
def project(client_as):
    lead = client_as("lead")
    return lead.post("/api/projects", json={"name": "GP", "industry": "gas_processing", "stage": "DD"}).json()["id"]


def test_link_scan_import_and_resync(client_as, project, folder):
    lead, eng, viewer = client_as("lead"), client_as("engineer"), client_as("viewer")
    assert eng.get(f"/api/projects/{project}/folder").json() == {"path": None}
    assert eng.get(f"/api/projects/{project}/folder/scan").json()["code"] == "folder_not_linked"
    assert eng.put(f"/api/projects/{project}/folder", json={"path": str(folder)}).status_code == 403   # faqat rahbar/administrator
    assert lead.put(f"/api/projects/{project}/folder", json={"path": str(folder)}).json() == {"path": str(folder)}

    scan = eng.get(f"/api/projects/{project}/folder/scan").json()
    files = {f["path"]: f for f in scan["files"]}
    assert len(files) == 7 and scan["truncated"] is False
    assert files["eski.dwg"]["status"] == "unsupported"
    assert "izoh.txt" not in files and not any(".git" in p or "~$" in p for p in files)
    pid = files["process/GP-PID-001_RevC.dxf"]
    assert (pid["status"], pid["doc_type"], pid["doc_number"], pid["revision"]) == ("new", "PID", "GP-PID-001", "C")

    assert viewer.post(f"/api/projects/{project}/folder/import", json={"files": []}).status_code == 403
    chosen = [{"path": p, "doc_type": f["doc_type"], "discipline": "process"} for p, f in files.items() if f["status"] == "new"]
    result = eng.post(f"/api/projects/{project}/folder/import", json={"files": chosen}).json()
    assert [r["status"] for r in result["results"]] == ["imported"] * 6
    docs = eng.get(f"/api/projects/{project}/documents").json()
    assert len(docs) == 6 and {d["parse_status"] for d in docs} == {"parsed"}
    assert next(d for d in docs if d["filename"] == "GP-PID-001_RevC.dxf")["doc_number"] == "GP-PID-001"

    # Qayta skanerlash: yuklanganlar belgilanadi; papkaga tushgan yangi fayl "new" bo'lib chiqadi
    (folder / "process" / "GP-DS-V999_RevA.pdf").write_bytes((folder / "process" / "GP-DS-V101_RevA.pdf").read_bytes() + b"\n")
    again = {f["path"]: f["status"] for f in eng.get(f"/api/projects/{project}/folder/scan").json()["files"]}
    assert again["process/GP-PID-001_RevC.dxf"] == "imported" and again["process/GP-DS-V999_RevA.pdf"] == "new"
    dup = eng.post(f"/api/projects/{project}/folder/import", json={"files": [chosen[0]]}).json()["results"][0]
    assert dup["status"] == "duplicate"


def test_import_cannot_escape_the_linked_folder(client_as, project, folder, tmp_path):
    lead = client_as("lead")
    secret = tmp_path / "maxfiy.pdf"; secret.write_bytes(b"%PDF-1.4 secret")
    lead.put(f"/api/projects/{project}/folder", json={"path": str(folder)})
    os.symlink(secret, folder / "havola.pdf")
    assert "havola.pdf" not in {f["path"] for f in lead.get(f"/api/projects/{project}/folder/scan").json()["files"]}
    for path in ("../maxfiy.pdf", str(secret), "havola.pdf", "yoq.pdf", "izoh.txt"):
        r = lead.post(f"/api/projects/{project}/folder/import",
                      json={"files": [{"path": path, "doc_type": "OTHER", "discipline": "technical"}]}).json()["results"][0]
        assert r["status"] == "error", path
    assert lead.get(f"/api/projects/{project}/documents").json() == []


def test_bad_folder_paths_are_rejected_with_clear_codes(client_as, project, tmp_path):
    lead = client_as("lead")
    put = lambda p: lead.put(f"/api/projects/{project}/folder", json={"path": p}).json().get("code")
    assert put("https://drive.google.com/drive/folders/abc") == "folder_is_url"
    assert put("hujjatlar/loyiha") == "folder_not_absolute"
    assert put(str(tmp_path / "yoq")) == "folder_not_found"
    f = tmp_path / "fayl.pdf"; f.write_bytes(b"x")
    assert put(str(f)) == "folder_not_found"
    assert lead.put(f"/api/projects/{project}/folder", json={"path": None}).json() == {"path": None}   # uzish


def test_linking_is_audited_and_folder_path_is_not_exported(client_as, project, folder):
    lead, admin = client_as("lead"), client_as("admin")
    lead.put(f"/api/projects/{project}/folder", json={"path": str(folder)})
    actions = [a["action"] for a in admin.get("/api/audit").json()]
    assert "project.folder_link" in actions
    assert "source_folder" not in lead.get(f"/api/projects/{project}").json()
