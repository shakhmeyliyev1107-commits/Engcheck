import json
import os
import sqlite3
import subprocess
import sys
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from engcheck.api.app import create_app
from engcheck.config import Settings
from engcheck.core import dbcrypt
from engcheck.core.auth import create_user
from engcheck.core.models import Project, Stage, User
from engcheck.core.secrets import SecretStore

MARKER = "MAXFIY-LOYIHA-NOMI-7731"


def _settings(tmp_path, encrypt=True):
    d = tmp_path / "data"; d.mkdir(exist_ok=True)
    return Settings(data_dir=d, db_url=f"sqlite:///{d / 'engcheck.db'}", encrypt=encrypt)


def _store(s):
    return SecretStore(s.data_dir, use_keyring=False)


# ---------- Host sarlavhasi ----------
@pytest.mark.parametrize("host,ok", [("127.0.0.1:8765", True), ("localhost:5000", True), ("[::1]:8765", True),
                                     ("127.0.0.1", True), ("evil.example", False), ("127.0.0.1.evil.example", False),
                                     ("attacker.com:8765", False), ("", False)])
def test_foreign_host_header_is_rejected(tmp_path, host, ok):
    with TestClient(create_app(_settings(tmp_path, encrypt=False)), base_url="http://127.0.0.1") as c:
        r = c.get("/api/setup", headers={"Host": host})
        assert (r.status_code == 200) is ok
        if not ok:
            assert r.status_code == 400 and r.json()["code"] == "bad_host"


# ---------- Shifrlash ----------
def test_new_database_is_encrypted_at_rest(tmp_path):
    s = _settings(tmp_path)
    factory, encrypted = dbcrypt.open_database(s, _store(s))
    assert encrypted is True
    with factory() as db:
        db.add(Project(name=MARKER, industry="gtl", stage=Stage.DD)); db.commit()
    raw = (s.data_dir / "engcheck.db").read_bytes()
    assert not raw.startswith(b"SQLite format 3") and MARKER.encode() not in raw
    with pytest.raises(sqlite3.DatabaseError):
        sqlite3.connect(s.data_dir / "engcheck.db").execute("select count(*) from projects")
    assert len(_store(s).get("db_key")) == 64


def test_encrypted_database_reopens_with_stored_key_and_fails_without(tmp_path):
    s = _settings(tmp_path)
    factory, _ = dbcrypt.open_database(s, _store(s))
    with factory() as db:
        db.add(Project(name="x", industry="gtl", stage=Stage.DD)); db.commit()
    factory.kw["bind"].dispose()
    factory2, encrypted = dbcrypt.open_database(s, _store(s))
    with factory2() as db:
        assert encrypted and db.query(Project).one().name == "x"
    factory2.kw["bind"].dispose()
    _store(s).delete("db_key")
    with pytest.raises(dbcrypt.DatabaseLocked):
        dbcrypt.open_database(s, _store(s))
    assert (s.data_dir / "engcheck.db").exists()               # kalit yo'q bo'lsa baza ustidan yangisi yozilmaydi


def test_encryption_off_or_unavailable_gives_plain_database(tmp_path, monkeypatch):
    s = _settings(tmp_path, encrypt=False)
    _, encrypted = dbcrypt.open_database(s, _store(s))
    assert encrypted is False and (s.data_dir / "engcheck.db").read_bytes().startswith(b"SQLite format 3")
    s2 = _settings(tmp_path / "b" if (tmp_path / "b").mkdir() is None else tmp_path)
    monkeypatch.setattr(dbcrypt, "sqlcipher_module", lambda: None)
    _, encrypted = dbcrypt.open_database(s2, _store(s2))
    assert encrypted is False and dbcrypt.available() is False


def test_existing_plain_database_keeps_working_then_encrypt_db_migrates_it(tmp_path):
    plain = _settings(tmp_path, encrypt=False)
    factory, _ = dbcrypt.open_database(plain, _store(plain))
    with factory() as db:
        db.add(Project(name=MARKER, industry="gtl", stage=Stage.DD))
        create_user(db, "aziz", "S3cret-pass", "engineer"); db.commit()
    factory.kw["bind"].dispose()
    s = _settings(tmp_path)                                    # shifrlash yoqilgan, lekin baza ochiq
    factory, encrypted = dbcrypt.open_database(s, _store(s))
    assert encrypted is False                                  # jim o'zgartirilmaydi
    factory.kw["bind"].dispose()

    backup = dbcrypt.encrypt_database(s, _store(s))
    assert backup.name == "engcheck.db.plain.bak" and backup.read_bytes().startswith(b"SQLite format 3")
    assert MARKER.encode() not in (s.data_dir / "engcheck.db").read_bytes()
    factory, encrypted = dbcrypt.open_database(s, _store(s))
    with factory() as db:
        assert encrypted and db.query(Project).one().name == MARKER and db.query(User).one().login == "aziz"
    with pytest.raises(dbcrypt.AlreadyEncrypted):
        dbcrypt.encrypt_database(s, _store(s))


def test_system_endpoint_reports_protection_level(tmp_path):
    s = _settings(tmp_path)
    app = create_app(s)
    with TestClient(app, base_url="http://127.0.0.1") as c:
        c.post("/api/setup", json={"login": "admin", "password": "S3cret-pass"})
        tok = c.post("/api/auth/login", json={"login": "admin", "password": "S3cret-pass"}).json()["token"]
        r = c.get("/api/system", headers={"Authorization": f"Bearer {tok}"}).json()
        assert r["db_encrypted"] is True and r["encryption_available"] is True and r["files_encrypted"] is False
        assert r["secret_backend"] in ("file", "keyring") and "db_key" not in json.dumps(r)
        assert c.get("/api/system").status_code == 401


# ---------- CLI: tasodifiy port va "ready" satri ----------
def test_cli_random_port_prints_ready_line_and_serves(tmp_path):
    env = {**os.environ, "ENGCHECK_ENCRYPT": "0"}
    proc = subprocess.Popen([sys.executable, "-m", "engcheck", "--port", "0", "--data-dir", str(tmp_path / "d")],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=env)
    try:
        deadline, ready = time.time() + 30, None
        while time.time() < deadline and ready is None:
            line = proc.stdout.readline()
            if line.strip().startswith("{"):
                ready = json.loads(line)
        assert ready and ready["event"] == "ready" and 1024 < ready["port"] < 65536
        r = httpx.get(f"http://127.0.0.1:{ready['port']}/api/setup", timeout=5, trust_env=False)
        assert r.json() == {"needs_setup": True} and (tmp_path / "d" / "engcheck.db").exists()
    finally:
        proc.terminate(); proc.wait(timeout=10)


def test_encrypted_connections_are_fast(tmp_path):
    """Har so'rov yangi ulanish ochadi: kalit hisobi (KDF) har safar bajarilsa, ilova sezilarli sekinlashadi."""
    from sqlalchemy import text
    s = _settings(tmp_path)
    factory, _ = dbcrypt.open_database(s, _store(s))
    engine = factory.kw["bind"]
    start = time.monotonic()
    for _ in range(40):
        engine.dispose()
        with engine.connect() as con:
            con.execute(text("select count(*) from projects"))
    assert time.monotonic() - start < 2.0


def test_encrypted_database_survives_concurrent_requests(tmp_path):
    """Xizmat so'rovlarni ko'p oqimda bajaradi: shifrlangan bazada ham ulanishlar bir-birini yopib qo'ymasligi kerak."""
    import threading
    s = _settings(tmp_path)
    factory, _ = dbcrypt.open_database(s, _store(s))
    with factory() as db:
        db.add(Project(name="x", industry="gtl", stage=Stage.DD)); db.commit()
    errors = []

    def work():
        try:
            for _ in range(15):
                with factory() as db:
                    assert db.query(Project).count() == 1
                    db.add(Project(name="y", industry="gtl", stage=Stage.DD)); db.rollback()
        except Exception as exc:   # noqa: BLE001
            errors.append(repr(exc))
    threads = [threading.Thread(target=work) for _ in range(16)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert errors == []
