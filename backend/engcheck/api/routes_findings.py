from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session as Db

from ..core import audit
from ..core.auth import Perm
from ..core.models import (Finding, FindingAction, FindingEvidence, FindingStatus, ReviewRun, Rule,
                           Severity, User)
from .deps import get_db, locale_of, require
from .errors import ApiError
from .routes_projects import get_project
from .serializers import finding_out

router = APIRouter()
S = FindingStatus
OPEN = (S.new, S.reviewed)
# amal -> (ruxsat etilgan boshlang'ich holatlar, yangi holat)
TRANSITIONS: dict[str, tuple[tuple[FindingStatus, ...], FindingStatus]] = {
    "review": ((S.new,), S.reviewed),
    "confirm": ((S.new, S.reviewed, S.rejected), S.confirmed),
    "reject": ((S.new, S.reviewed, S.confirmed), S.rejected),
    "mark_fixed": ((S.confirmed,), S.fixed),
}


class ActionBody(BaseModel):
    action: Literal["review", "confirm", "reject", "mark_fixed"]
    comment: str = ""


def latest_run(db: Db, project_id: int) -> ReviewRun | None:
    return db.query(ReviewRun).filter_by(project_id=project_id).order_by(ReviewRun.id.desc()).first()


def _user_names(db: Db) -> dict[int, str]:
    return {u.id: u.login for u in db.query(User)}


@router.get("/projects/{project_id}/findings")
def list_findings(project_id: int, request: Request,
                  severity: Severity | None = None,
                  status: Literal["new", "reviewed", "confirmed", "rejected", "fixed", "open"] | None = None,
                  rule: str | None = None, document_id: int | None = None, tag: str | None = None,
                  _: User = Depends(require(Perm.view)), db: Db = Depends(get_db)):
    get_project(db, project_id)
    run = latest_run(db, project_id)
    if run is None:
        return []
    q = db.query(Finding).filter(Finding.run_id == run.id)
    if severity:
        q = q.filter(Finding.severity == severity)
    if status == "open":
        q = q.filter(Finding.status.in_(OPEN))
    elif status:
        q = q.filter(Finding.status == status)
    if rule:
        q = q.join(Rule, Finding.rule_id == Rule.id).filter(Rule.code == rule)
    if tag:
        q = q.filter(Finding.tag_text == tag)
    if document_id is not None:
        q = q.filter(Finding.id.in_(db.query(FindingEvidence.finding_id)
                                    .filter(FindingEvidence.document_id == document_id)))
    order = {"critical": 0, "major": 1, "minor": 2, "info": 3}
    items = sorted(q.all(), key=lambda f: (order[str(f.severity)], f.id))
    return [finding_out(f, locale_of(request)) for f in items]


def _get(db: Db, finding_id: int) -> Finding:
    finding = db.get(Finding, finding_id)
    if finding is None:
        raise ApiError(404, "not_found")
    return finding


@router.get("/findings/{finding_id}")
def read_finding(finding_id: int, request: Request, _: User = Depends(require(Perm.view)),
                 db: Db = Depends(get_db)):
    return finding_out(_get(db, finding_id), locale_of(request), detail=True, users=_user_names(db))


@router.post("/findings/{finding_id}/actions")
def act(finding_id: int, body: ActionBody, request: Request,
        user: User = Depends(require(Perm.decide)), db: Db = Depends(get_db)):
    finding = _get(db, finding_id)
    allowed_from, target = TRANSITIONS[body.action]
    comment = body.comment.strip()
    if body.action == "reject" and not comment:
        raise ApiError(422, "comment_required")
    if finding.status not in allowed_from:
        raise ApiError(409, "invalid_transition")
    previous = str(finding.status)
    finding.status = target
    finding.actions.append(FindingAction(user_id=user.id, action=body.action, comment=comment))
    db.flush()
    audit.record(db, user.id, f"finding.{body.action}", "finding", finding.id,
                 {"from": previous, "to": str(target), "comment": comment})
    return finding_out(finding, locale_of(request), detail=True, users=_user_names(db))
