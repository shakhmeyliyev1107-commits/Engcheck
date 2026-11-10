"""Faqat qo'shiladigan, xesh-zanjirli audit jurnali."""
import hashlib
import json

from sqlalchemy.orm import Session as Db

from .models import AuditLog, utcnow

GENESIS = "0" * 64


def _digest(prev_hash: str, row: AuditLog) -> str:
    payload = json.dumps(
        [row.user_id, row.action, row.object_type, row.object_id, row.details,
         row.created_at.isoformat()],
        sort_keys=True, ensure_ascii=False)
    return hashlib.sha256((prev_hash + payload).encode()).hexdigest()


def record(db: Db, user_id: int | None, action: str, object_type: str,
           object_id: int | None, details: dict | None = None) -> AuditLog:
    last = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    prev = last.hash if last else GENESIS
    row = AuditLog(user_id=user_id, action=action, object_type=object_type, object_id=object_id,
                   details=details, created_at=utcnow(), prev_hash=prev, hash="")
    row.hash = _digest(prev, row)
    db.add(row)
    db.flush()
    return row


def verify(db: Db) -> int | None:
    """Zanjir butun bo'lsa None, aks holda birinchi buzilgan yozuv id si."""
    prev = GENESIS
    for row in db.query(AuditLog).order_by(AuditLog.id):
        if row.prev_hash != prev or row.hash != _digest(prev, row):
            return row.id
        prev = row.hash
    return None
