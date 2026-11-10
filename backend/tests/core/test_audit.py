from engcheck.core.audit import record, verify
from engcheck.core.models import AuditLog


def _three(db):
    for i in range(1, 4):
        record(db, 1, "finding.confirm", "finding", i, {"comment": "ok"})


def test_chain_verifies(db):
    _three(db)
    assert verify(db) is None
    rows = db.query(AuditLog).order_by(AuditLog.id).all()
    assert rows[0].prev_hash == "0" * 64
    assert rows[1].prev_hash == rows[0].hash


def test_empty_log_verifies(db):
    assert verify(db) is None


def test_detects_tampered_details(db):
    _three(db)
    row = db.get(AuditLog, 2)
    row.details = {"comment": "o'zgartirildi"}
    db.flush()
    assert verify(db) == 2


def test_detects_deleted_row(db):
    _three(db)
    db.delete(db.get(AuditLog, 2))
    db.flush()
    assert verify(db) == 3


def test_survives_commit_and_reload(db):
    _three(db)
    db.commit()
    db.expire_all()
    assert verify(db) is None
