from collections import Counter

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session as Db

from ..core.auth import Perm
from ..core.models import Document, Finding, FindingStatus, KbSource, Rule, Severity, User
from ..review.engine import seed_rules
from .deps import get_db, locale_of, require
from .serializers import run_out
from .routes_findings import OPEN, latest_run
from .routes_projects import get_project

router = APIRouter()


@router.get("/projects/{project_id}/dashboard")
def dashboard(project_id: int, request: Request, _: User = Depends(require(Perm.view)), db: Db = Depends(get_db)):
    get_project(db, project_id)
    seed_rules(db)
    docs = db.query(Document).filter_by(project_id=project_id).all()
    run = latest_run(db, project_id)
    findings = db.query(Finding).filter_by(run_id=run.id).all() if run else []
    by_severity = Counter(str(f.severity) for f in findings)
    by_status = Counter(str(f.status) for f in findings)
    open_items = [f for f in findings if f.status in OPEN]
    rules = db.query(Rule).all()
    return {
        "documents": {"total": len(docs),
                      "by_type": dict(Counter(str(d.doc_type) for d in docs)),
                      "by_status": dict(Counter(str(d.parse_status) for d in docs))},
        "findings": {"total": len(findings),
                     "by_severity": {s.value: by_severity.get(s.value, 0) for s in Severity},
                     "by_status": {s.value: by_status.get(s.value, 0) for s in FindingStatus},
                     "open": len(open_items),
                     "open_critical": sum(1 for f in open_items if f.severity == Severity.critical),
                     "confirmed_unfixed": by_status.get("confirmed", 0),
                     "ai": sum(1 for f in findings if f.source_type == "ai")},
        "last_run": None if run is None else run_out(run, locale_of(request)),
        "kb": {"sources": db.query(KbSource).filter_by(approved=True).count(),
               "pending": db.query(KbSource).filter_by(approved=False).count()},
        "rules": {"enabled": sum(1 for r in rules if r.enabled), "total": len(rules)},
    }
