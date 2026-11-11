"""3-sikl yakuniy ko'rigida topilgan holatlar."""
import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from engcheck.api.app import create_app
from engcheck.config import Settings
from engcheck.core import dbcrypt
from engcheck.core.models import Document, FindingAction, Project, Stage
from engcheck.core.secrets import SecretStore
from engcheck.package import service as pkg

from .test_package import _rezip, exported, other  # noqa: F401  (fixturalar)


def _files(settings):
    root = settings.data_dir / "files"
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()) if root.exists() else []


def _edit(raw, fn):
    def mutate(entries):
        m = json.loads(entries["manifest.json"]); fn(m, entries); entries["manifest.json"] = json.dumps(m).encode()
    return _rezip(raw, mutate)


@pytest.fixture
def raw(db, settings, project, exported):  # noqa: F811
    return pkg.export_project(db, settings, project.id, exported, None)


# 1 — xato bo'lsa diskda hech narsa qolmaydi
def test_failure_after_ingest_started_removes_copied_files(raw, other, monkeypatch):  # noqa: F811
    odb, osettings, ouser = other

    def boom(*a, **k):
        raise RuntimeError("tekshiruv yiqildi")
    monkeypatch.setattr(pkg, "run_review", boom)
    with pytest.raises(RuntimeError):
        pkg.import_project(odb, osettings, ouser, raw, None)
    odb.rollback()
    assert _files(osettings) == [] and odb.query(Project).count() == 0 and odb.query(Document).count() == 0


# 2 — noto'g'ri paket har doim PackageError, hech qachon boshqa istisno
@pytest.mark.parametrize("fn", [
    lambda m, e: m["decisions"].append({"fingerprint": ["x"], "status": "confirmed", "actions": []}),
    lambda m, e: m["decisions"][0].__setitem__("actions", 5),
    lambda m, e: m["decisions"][0].__setitem__("actions", [{"action": "confirm", "comment": 5, "user": []}]),
    lambda m, e: m["decisions"].append("satr"),
    lambda m, e: m["documents"][0].__setitem__("doc_number", ["a"]),
    lambda m, e: m["documents"][0].__setitem__("revision", {"a": 1}),
    lambda m, e: m["documents"][0].__setitem__("filename", "a\x00b.pdf"),
    lambda m, e: m["documents"][0].__setitem__("filename", "a." + "x" * 250),
    lambda m, e: m["documents"][0].__setitem__("filename", "x" * 400 + ".pdf"),
    lambda m, e: m["documents"][0].__setitem__("doc_number", "N" * 500),
    lambda m, e: m["documents"][0].__setitem__("sha256", 5),
    lambda m, e: m["project"].__setitem__("name", ["a"]),
    lambda m, e: m["project"].__setitem__("industry", "x" * 500),
    lambda m, e: m.__setitem__("documents", "hammasi"),
    lambda m, e: m.__setitem__("decisions", {"a": 1}),
])
def test_malformed_manifest_fields_are_package_errors(raw, other, fn):  # noqa: F811
    odb, osettings, ouser = other
    with pytest.raises(pkg.PackageError) as e:
        pkg.import_project(odb, osettings, ouser, _edit(raw, fn), None)
    assert e.value.code == "invalid_package"
    odb.rollback()
    assert _files(osettings) == [] and odb.query(Project).count() == 0


def test_corrupt_compressed_stream_and_deep_nesting_are_package_errors(raw, other):  # noqa: F811
    odb, osettings, ouser = other
    data = bytearray(raw)
    z = zipfile.ZipFile(io.BytesIO(raw))
    info = max((i for i in z.infolist() if i.filename != "manifest.json"), key=lambda i: i.compress_size)
    start = info.header_offset + 30 + len(info.filename.encode()) + 4
    for k in range(start, start + 40):
        data[k] ^= 0xFF                                       # siqilgan oqim buzildi (yuklab olishda shikastlangan fayl)
    with pytest.raises(pkg.PackageError) as e:
        pkg.import_project(odb, osettings, ouser, bytes(data), None)
    assert e.value.code in ("invalid_package", "checksum_mismatch")
    deep = "[" * 100000 + "]" * 100000
    with pytest.raises(pkg.PackageError):
        pkg.import_project(odb, osettings, ouser, _rezip(raw, lambda en: en.__setitem__("manifest.json", deep.encode())), None)
    assert _files(osettings) == []


# 3 — takroriy yozuvlar va hajm
def test_duplicate_documents_and_too_many_entries_are_rejected(raw, other, monkeypatch):  # noqa: F811
    odb, osettings, ouser = other
    with pytest.raises(pkg.PackageError) as e:
        pkg.import_project(odb, osettings, ouser, _edit(raw, lambda m, en: m["documents"].extend([m["documents"][0]] * 3000)), None)
    assert e.value.code in ("invalid_package", "too_large")
    with pytest.raises(pkg.PackageError):
        pkg.import_project(odb, osettings, ouser, _edit(raw, lambda m, en: m["documents"].append(dict(m["documents"][0]))), None)
    monkeypatch.setattr(pkg, "MAX_MANIFEST_BYTES", 100)
    with pytest.raises(pkg.PackageError) as e:
        pkg.import_project(odb, osettings, ouser, raw, None)
    assert e.value.code == "too_large"


def test_actual_decompressed_size_is_bounded_even_if_header_lies(raw, other, monkeypatch):  # noqa: F811
    odb, osettings, ouser = other
    monkeypatch.setattr(pkg, "MAX_TOTAL_BYTES", 10 * 1024 * 1024)
    real_infolist = zipfile.ZipFile.infolist

    def lying(self):                                           # sarlavha kichik hajmni e'lon qiladi
        infos = real_infolist(self)
        return [type("I", (), {"file_size": 1, "filename": i.filename})() for i in infos]
    monkeypatch.setattr(pkg, "MAX_TOTAL_BYTES", 2000)
    monkeypatch.setattr(zipfile.ZipFile, "infolist", lying)
    with pytest.raises(pkg.PackageError) as e:
        pkg.import_project(odb, osettings, ouser, raw, None)
    assert e.value.code == "too_large" and _files(osettings) == []


def test_import_accepts_a_file_path_and_reports_ingested_count(raw, other, tmp_path):  # noqa: F811
    odb, osettings, ouser = other
    p = tmp_path / "p.engpkg"; p.write_bytes(raw)
    assert pkg.import_project(odb, osettings, ouser, p, None).documents == 6


# 9 — qaror tiklash chegaralari
def test_reviewed_is_not_restored_and_actions_are_capped(raw, other):  # noqa: F811
    odb, osettings, ouser = other

    def fn(m, en):
        m["decisions"][0]["actions"] = [{"action": "confirm", "comment": "c", "user": "u"}] * 500
        m["decisions"][1]["status"] = "reviewed"
    r = pkg.import_project(odb, osettings, ouser, _edit(raw, fn), None)
    assert (r.decisions_restored, r.decisions_unmatched) == (1, 1)
    assert odb.query(FindingAction).count() <= pkg.MAX_ACTIONS


# 6 — encrypt-db uzilishdan keyin ma'lumot yo'qolmaydi
def test_leftover_migration_files_block_startup_instead_of_creating_empty_db(tmp_path):
    d = tmp_path / "data"; d.mkdir()
    s = Settings(data_dir=d, db_url=f"sqlite:///{d / 'engcheck.db'}", encrypt=True)
    (d / "engcheck.db.plain.bak").write_bytes(b"SQLite format 3\x00" + b"\0" * 100)
    (d / "engcheck.db.encrypting").write_bytes(b"x" * 100)
    with pytest.raises(dbcrypt.DatabaseLocked):
        dbcrypt.open_database(s, SecretStore(d, use_keyring=False))
    assert not (d / "engcheck.db").exists()


def test_encrypt_db_keeps_plain_copy_in_place_until_encrypted_one_is_ready(tmp_path, monkeypatch):
    d = tmp_path / "data"; d.mkdir()
    plain = Settings(data_dir=d, db_url=f"sqlite:///{d / 'engcheck.db'}", encrypt=False)
    store = SecretStore(d, use_keyring=False)
    factory, _ = dbcrypt.open_database(plain, store)
    with factory() as db:
        db.add(Project(name="muhim", industry="gtl", stage=Stage.DD)); db.commit()
    factory.kw["bind"].dispose()
    monkeypatch.setattr(dbcrypt, "_verify", lambda *a: (_ for _ in ()).throw(RuntimeError("mos kelmadi")))
    with pytest.raises(RuntimeError):
        dbcrypt.encrypt_database(plain, store)
    assert dbcrypt.is_plain(d / "engcheck.db") and not (d / "engcheck.db.encrypting").exists()   # asl baza joyida
    factory, encrypted = dbcrypt.open_database(plain, store)
    with factory() as db:
        assert not encrypted and db.query(Project).one().name == "muhim"


# 8 — Host: port faqat raqam
@pytest.mark.parametrize("host", ["127.0.0.1:80@evil.com", "localhost:evil.com", "127.0.0.1:"])
def test_host_port_must_be_numeric(tmp_path, host):
    d = tmp_path / "data"; d.mkdir()
    s = Settings(data_dir=d, db_url=f"sqlite:///{d / 'engcheck.db'}", encrypt=False)
    with TestClient(create_app(s), base_url="http://127.0.0.1") as c:
        assert c.get("/api/setup", headers={"Host": host}).status_code == 400
