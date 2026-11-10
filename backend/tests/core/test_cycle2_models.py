import sqlite3
import stat

import pytest
from sqlalchemy import inspect

from engcheck.core.db import init_db
from engcheck.core.models import AiProvider, FindingAiNote, KbChunk, KbSource, Project, ReviewRun, Stage
from engcheck.core.secrets import SecretStore


def test_new_tables_and_defaults(db):
    p = Project(name="x", industry="gtl", stage=Stage.FEED)
    src = KbSource(title="API 571", kind="standard", standard_code="API RP 571", edition="2020")
    prov = AiProvider(name="lokal", kind="ollama", base_url="http://127.0.0.1:11434", model="llama3")
    db.add_all([p, src, prov])
    db.flush()
    assert p.allow_cloud_ai is False                      # bulutli AI standart holatda o'chiq
    assert (src.status, src.license_type, src.approved) == ("active", "internal", False)
    assert prov.enabled is True and prov.is_default is False
    db.add(KbChunk(source_id=src.id, ordinal=0, page_no=1, text="matn"))
    db.flush()
    assert {c.name for c in ReviewRun.__table__.columns} >= {"ai_provider", "ai_note"}
    assert FindingAiNote.__tablename__ == "finding_ai_notes"


def test_existing_cycle1_database_gets_new_columns_without_data_loss(tmp_path):
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE projects (id INTEGER PRIMARY KEY, name VARCHAR(200) NOT NULL, industry VARCHAR(40) NOT NULL,
                               stage VARCHAR(16) NOT NULL, created_by INTEGER, created_at DATETIME);
        INSERT INTO projects (name, industry, stage) VALUES ('Eski loyiha', 'gtl', 'DD');
    """)
    con.commit(); con.close()
    factory = init_db(f"sqlite:///{path}")
    with factory() as db:
        p = db.query(Project).one()
        assert p.name == "Eski loyiha" and p.allow_cloud_ai is False
    cols = {c["name"] for c in inspect(factory.kw["bind"]).get_columns("projects")}
    assert "allow_cloud_ai" in cols
    init_db(f"sqlite:///{path}")                          # ikkinchi marta ham xatosiz


@pytest.fixture
def store(tmp_path):
    return SecretStore(tmp_path, use_keyring=False)


def test_secret_roundtrip_and_delete(store):
    assert store.get("provider:1") is None
    store.set("provider:1", "sk-test-123")
    assert store.get("provider:1") == "sk-test-123"
    store.set("provider:1", "sk-new")
    assert store.get("provider:1") == "sk-new"
    store.delete("provider:1")
    assert store.get("provider:1") is None
    store.delete("provider:1")                            # yo'q kalitni o'chirish xato emas


def test_secret_is_not_stored_in_plain_text_and_files_are_private(store, tmp_path):
    store.set("provider:1", "sk-very-secret-value")
    blob = b"".join(f.read_bytes() for f in tmp_path.iterdir() if f.is_file())
    assert b"sk-very-secret-value" not in blob
    for f in tmp_path.iterdir():
        assert stat.S_IMODE(f.stat().st_mode) == 0o600, f.name


def test_secret_survives_reopen(store, tmp_path):
    store.set("provider:2", "abc")
    assert SecretStore(tmp_path, use_keyring=False).get("provider:2") == "abc"
    assert store.backend == "file"


def test_corrupt_secret_file_reads_as_empty_not_crash(store, tmp_path):
    store.set("provider:1", "abc")
    (tmp_path / "secrets.enc").write_bytes(b"garbage")
    assert SecretStore(tmp_path, use_keyring=False).get("provider:1") is None
