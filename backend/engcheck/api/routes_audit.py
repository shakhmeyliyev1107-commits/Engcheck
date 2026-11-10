from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as Db

from ..core import audit
from ..core.auth import Perm
from ..core.models import AuditLog, User
from .deps import get_db, require

router = APIRouter()


@router.get("/audit")
def list_audit(limit: int = Query(200, ge=1, le=1000), _: User = Depends(require(Perm.manage_users)),
               db: Db = Depends(get_db)):
    names = {u.id: u.login for u in db.query(User)}
    rows = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    return [{"id": r.id, "user": names.get(r.user_id), "action": r.action, "object_type": r.object_type,
             "object_id": r.object_id, "details": r.details, "created_at": r.created_at.isoformat()}
            for r in rows]


@router.get("/audit/verify")
def verify_audit(_: User = Depends(require(Perm.manage_users)), db: Db = Depends(get_db)):
    broken = audit.verify(db)
    return {"ok": broken is None, "broken_at": broken}
