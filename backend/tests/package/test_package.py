import io
import json
import zipfile

import pytest

from engcheck.config import Settings
from engcheck.core.auth import create_user
from engcheck.core.db import init_db
from engcheck.core.models import (AiProvider, AuditLog, Document, Finding, FindingAction, FindingStatus, Project,
                                  ReviewRun, Stage)
from engcheck.kb.service import add_source
from engcheck.package import service as pkg
from engcheck.review.engine import run_review


@pytest.fixture
def exported(db, settings, project, ingest_sample):
    """Namunaviy loyiha: tekshirilgan, ikki topilma bo'yicha qaror qilingan."""
    user = create_user(db, "nodira", "S3cret-pass", "lead")
    run = run_review(db, project.id, user.id)
    findings = {(f.rule.code, f.tag_text): f for f in db.query(Finding).filter_by(run_id=run.id)}
    a, b = findings[("R001", "V-101")], findings[("R003", "P-101B")]
    a.status = FindingStatus.confirmed
    a.actions.append(FindingAction(user_id=user.id, action="confirm", comment="datasheet xato"))
    b.status = FindingStatus.rejected
    b.actions.append(FindingAction(user_id=user.id, action="reject", comment="vendor keyin beradi"))
    project.allow_cloud_ai = True
    db.add(AiProvider(name="bulut", kind="openai_compatible", base_url="https://api.example.com/v1", model="m"))
    add_source(db, settings, user, "ASME VIII", "standard", text="Licensed clause text.", license_type="licensed")
    db.flush()
    return user


@pytest.fixture
def other(tmp_path):
    """Hamkasbning alohida, bo'sh bazasi."""
    d = tmp_path / "other"; d.mkdir()
    s = Settings(data_dir=d, db_url=f"sqlite:///{d / 'engcheck.db'}", encrypt=False)
    with init_db(s.db_url)() as session:
        yield session, s, create_user(session, "aziz", "S3cret-pass", "engineer")


def _state(db, project_id):
    run = db.query(ReviewRun).filter_by(project_id=project_id).order_by(ReviewRun.id.desc()).first()
    return sorted(((f.rule.code, f.tag_text, f.param, str(f.status)) for f in db.query(Finding).filter_by(run_id=run.id)), key=str)


@pytest.mark.parametrize("passphrase", [None, "to'g'ri ot batareya"])
def test_roundtrip_restores_documents_findings_and_decisions(db, settings, project, exported, other, passphrase):
    data = pkg.export_project(db, settings, project.id, exported, passphrase)
    odb, osettings, ouser = other
    result = pkg.import_project(odb, osettings, ouser, data, passphrase)
    new = odb.get(Project, result.project_id)
    assert (new.name, new.industry, str(new.stage)) == (project.name, project.industry, str(project.stage))
    assert new.allow_cloud_ai is False                                 # bulut roziligi ko'chmaydi
    assert odb.query(Document).filter_by(project_id=new.id).count() == 6
    assert _state(odb, new.id) == _state(db, project.id)
    assert (result.documents, result.decisions_restored, result.decisions_unmatched) == (6, 2, 0)
    f = next(f for f in odb.query(Finding) if f.tag_text == "V-101" and f.rule.code == "R001")
    assert [(a.action, a.comment) for a in f.actions] == [("imported", "nodira: datasheet xato")]
    actions = [r.action for r in odb.query(AuditLog)]
    assert "project.import" in actions and "project.export" in [r.action for r in db.query(AuditLog)]


def test_originals_are_byte_identical_in_package(db, settings, project, exported, sample_docs):
    z = zipfile.ZipFile(io.BytesIO(pkg.export_project(db, settings, project.id, exported, None)))
    manifest = json.loads(z.read("manifest.json"))
    assert manifest["format"] == 1 and len(manifest["documents"]) == 6
    by_name = {d["filename"]: d for d in manifest["documents"]}
    for d in sample_docs:
        assert z.read(by_name[d.path.name]["path"]) == d.path.read_bytes()


def test_excluded_data_is_not_in_package(db, settings, project, exported):
    raw = pkg.export_project(db, settings, project.id, exported, None)
    z = zipfile.ZipFile(io.BytesIO(raw))
    text = z.read("manifest.json").decode()
    for secret in ("password", "api.example.com", "Licensed clause", "bulut", "allow_cloud_ai", "token"):
        assert secret not in text
    assert all(n == "manifest.json" or n.startswith("files/") for n in z.namelist())


def test_passphrase_package_is_opaque_and_wrong_passphrase_fails(db, settings, project, exported, other):
    data = pkg.export_project(db, settings, project.id, exported, "parol-123")
    assert not data.startswith(b"PK") and b"GP-PID-001" not in data and b"manifest" not in data
    odb, osettings, ouser = other
    for bad in ("boshqa", None, ""):
        with pytest.raises(pkg.PackageError) as e:
            pkg.import_project(odb, osettings, ouser, data, bad)
        assert e.value.code == ("passphrase_required" if not bad else "wrong_passphrase")
    assert odb.query(Project).count() == 0


def _rezip(raw, mutate):
    src = zipfile.ZipFile(io.BytesIO(raw))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as dst:
        entries = {n: src.read(n) for n in src.namelist()}
        mutate(entries)
        for n, b in entries.items():
            dst.writestr(n, b)
    return out.getvalue()


def test_tampered_file_is_detected_and_nothing_is_imported(db, settings, project, exported, other):
    raw = pkg.export_project(db, settings, project.id, exported, None)

    def flip(entries):
        name = next(n for n in entries if n.endswith(".xlsx"))
        entries[name] = entries[name][:-1] + bytes([entries[name][-1] ^ 1])
    odb, osettings, ouser = other
    with pytest.raises(pkg.PackageError) as e:
        pkg.import_project(odb, osettings, ouser, _rezip(raw, flip), None)
    assert e.value.code == "checksum_mismatch"
    odb.rollback()
    assert odb.query(Project).count() == 0 and not list((osettings.data_dir / "files").glob("*/*")) if (osettings.data_dir / "files").exists() else True


@pytest.mark.parametrize("path", ["../../evil.dxf", "/etc/passwd", "files/../../x", "files\\..\\x"])
def test_path_traversal_in_manifest_is_rejected(db, settings, project, exported, other, path, tmp_path):
    raw = pkg.export_project(db, settings, project.id, exported, None)

    def evil(entries):
        m = json.loads(entries["manifest.json"])
        old = m["documents"][0]["path"]
        m["documents"][0]["path"] = path
        entries[path] = entries.pop(old)
        entries["manifest.json"] = json.dumps(m).encode()
    odb, osettings, ouser = other
    with pytest.raises(pkg.PackageError) as e:
        pkg.import_project(odb, osettings, ouser, _rezip(raw, evil), None)
    assert e.value.code == "invalid_package"


@pytest.mark.parametrize("data,code", [(b"", "invalid_package"), (b"not a zip at all", "invalid_package"),
                                       (b"PK\x03\x04broken", "invalid_package")])
def test_garbage_is_rejected(other, data, code):
    odb, osettings, ouser = other
    with pytest.raises(pkg.PackageError) as e:
        pkg.import_project(odb, osettings, ouser, data, None)
    assert e.value.code == code


def test_zip_without_or_with_bad_manifest_and_future_format(db, settings, project, exported, other):
    odb, osettings, ouser = other
    raw = pkg.export_project(db, settings, project.id, exported, None)
    for mutate in (lambda e: e.pop("manifest.json"),
                   lambda e: e.__setitem__("manifest.json", b"{not json"),
                   lambda e: e.__setitem__("manifest.json", json.dumps({"format": 1, "project": {}}).encode())):
        with pytest.raises(pkg.PackageError) as e:
            pkg.import_project(odb, osettings, ouser, _rezip(raw, mutate), None)
        assert e.value.code == "invalid_package"

    def future(e):
        m = json.loads(e["manifest.json"]); m["format"] = 99; e["manifest.json"] = json.dumps(m).encode()
    with pytest.raises(pkg.PackageError) as e:
        pkg.import_project(odb, osettings, ouser, _rezip(raw, future), None)
    assert e.value.code == "unsupported_format"


def test_oversized_package_is_rejected_before_extraction(db, settings, project, exported, other, monkeypatch):
    raw = pkg.export_project(db, settings, project.id, exported, None)
    monkeypatch.setattr(pkg, "MAX_TOTAL_BYTES", 1000)
    odb, osettings, ouser = other
    with pytest.raises(pkg.PackageError) as e:
        pkg.import_project(odb, osettings, ouser, raw, None)
    assert e.value.code == "too_large"
    monkeypatch.setattr(pkg, "MAX_TOTAL_BYTES", 2 * 1024 ** 3); monkeypatch.setattr(pkg, "MAX_FILES", 3)
    with pytest.raises(pkg.PackageError) as e:
        pkg.import_project(odb, osettings, ouser, raw, None)
    assert e.value.code == "too_large"


def test_unmatched_decisions_are_counted_not_lost_silently(db, settings, project, exported, other):
    raw = pkg.export_project(db, settings, project.id, exported, None)

    def ghost(e):
        m = json.loads(e["manifest.json"])
        m["decisions"].append({"fingerprint": "0" * 64, "status": "confirmed", "rule": "R001", "tag": "X-999",
                               "actions": [{"action": "confirm", "comment": "", "user": "kim"}]})
        e["manifest.json"] = json.dumps(m).encode()
    odb, osettings, ouser = other
    result = pkg.import_project(odb, osettings, ouser, _rezip(raw, ghost), None)
    assert (result.decisions_restored, result.decisions_unmatched) == (2, 1)


def test_import_same_package_twice_makes_two_projects(db, settings, project, exported, other):
    raw = pkg.export_project(db, settings, project.id, exported, None)
    odb, osettings, ouser = other
    a = pkg.import_project(odb, osettings, ouser, raw, None)
    b = pkg.import_project(odb, osettings, ouser, raw, None)
    assert a.project_id != b.project_id and odb.query(Document).count() == 12
