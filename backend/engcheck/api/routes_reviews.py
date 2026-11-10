from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session as Db

from ..core import audit
from ..core.auth import Perm
from ..core.models import Rule, User
from ..review.engine import run_review, seed_rules
from .deps import get_db, locale_of, require
from .errors import ApiError
from .routes_projects import get_project
from .routes_ai import resolve_for
from .serializers import rule_out, run_out

router = APIRouter()


class RulePatch(BaseModel):
    enabled: bool


class ReviewBody(BaseModel):
    use_ai: bool = False


@router.post("/projects/{project_id}/reviews", status_code=201)
def start_review(project_id: int, request: Request, body: ReviewBody | None = None,
                 user: User = Depends(require(Perm.review)), db: Db = Depends(get_db)):
    project = get_project(db, project_id)
    resolution = resolve_for(request, db, project) if body and body.use_ai else None
    run = run_review(db, project_id, user.id, resolution=resolution, locale=locale_of(request))
    return run_out(run, locale_of(request))


@router.get("/rules")
def list_rules(request: Request, _: User = Depends(require(Perm.view)), db: Db = Depends(get_db)):
    seed_rules(db)
    return [rule_out(r, locale_of(request)) for r in db.query(Rule).order_by(Rule.code)]


@router.patch("/rules/{code}")
def update_rule(code: str, body: RulePatch, request: Request,
                user: User = Depends(require(Perm.manage_rules)), db: Db = Depends(get_db)):
    seed_rules(db)
    rule = db.query(Rule).filter_by(code=code).first()
    if rule is None:
        raise ApiError(404, "not_found")
    rule.enabled = body.enabled
    audit.record(db, user.id, "rule.update", "rule", rule.id, {"code": code, "enabled": body.enabled})
    return rule_out(rule, locale_of(request))
