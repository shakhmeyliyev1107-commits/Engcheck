from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session as Db

from ..core import audit
from ..core.auth import Perm
from ..ai.assist import AssistError, explain_finding
from ..core.models import (DocType, FindingAiNote, Document, Finding, FindingAction, FindingEvidence, FindingStatus, ReviewRun, Rule,
                           Severity, User)
from .deps import get_db, locale_of, require
from .errors import ApiError
from .routes_projects import get_project
from ..kb.service import KbError, propose_lesson
from .errors import ai_reason
from .routes_ai import resolve_for
from .serializers import ai_note_out, finding_out, kb_source_out

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


def _detail(db: Db, finding: Finding, locale: str) -> dict:
    users = {u.id: u.login for u in db.query(User)}
    out = finding_out(finding, locale, detail=True, users=users)
    out["project_id"] = db.get(ReviewRun, finding.run_id).project_id
    notes = db.query(FindingAiNote).filter_by(finding_id=finding.id).order_by(FindingAiNote.id.desc())
    out["ai_notes"] = [ai_note_out(n, users) for n in notes]
    return out


@router.get("/projects/{project_id}/findings")
def list_findings(project_id: int, request: Request,
                  severity: Severity | None = None,
                  status: Literal["new", "reviewed", "confirmed", "rejected", "fixed", "open"] | None = None,
                  rule: str | None = None, document_id: int | None = None, tag: str | None = None,
                  doc_type: DocType | None = None,
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
    if doc_type is not None:
        q = q.filter(Finding.id.in_(
            db.query(FindingEvidence.finding_id).join(Document, FindingEvidence.document_id == Document.id)
            .filter(Document.doc_type == doc_type)))
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
    return _detail(db, _get(db, finding_id), locale_of(request))


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
    return _detail(db, finding, locale_of(request))


class DecisionBody(BaseModel):
    decision: Literal["accepted", "rejected"]


class LessonBody(BaseModel):
    text: str | None = None


@router.post("/findings/{finding_id}/ai-notes", status_code=201)
def request_ai_note(finding_id: int, request: Request, user: User = Depends(require(Perm.review)),
                    db: Db = Depends(get_db)):
    """Topilmaga AI izohi so'raydi. Izoh 'proposed' holatida saqlanadi; topilma holati o'zgarmaydi."""
    finding = _get(db, finding_id)
    project = db.get(ReviewRun, finding.run_id)
    from ..core.models import Project
    resolution = resolve_for(request, db, db.get(Project, project.project_id))
    locale = locale_of(request)
    try:
        note = explain_finding(db, finding, user, locale, resolution)
    except AssistError as exc:
        if exc.code == "bad_response":
            raise ApiError(502, "ai_bad_response") from exc
        raise ApiError(503, "ai_unavailable", reason=ai_reason(exc.code, locale)) from exc
    return ai_note_out(note, {user.id: user.login})


@router.post("/ai-notes/{note_id}/decision")
def decide_ai_note(note_id: int, body: DecisionBody, user: User = Depends(require(Perm.decide)),
                   db: Db = Depends(get_db)):
    note = db.get(FindingAiNote, note_id)
    if note is None:
        raise ApiError(404, "not_found")
    note.status, note.decided_by = body.decision, user.id
    audit.record(db, user.id, f"ai_note.{body.decision}", "ai_note", note.id, {"finding_id": note.finding_id})
    return ai_note_out(note, {u.id: u.login for u in db.query(User)})


@router.post("/findings/{finding_id}/lesson", status_code=201)
def lesson(finding_id: int, body: LessonBody, request: Request, user: User = Depends(require(Perm.decide)),
           db: Db = Depends(get_db)):
    try:
        source = propose_lesson(db, request.app.state.settings, _get(db, finding_id), user, body.text)
    except KbError as exc:
        raise ApiError(409, "lesson_not_allowed") from exc
    return kb_source_out(source, {user.id: user.login})
