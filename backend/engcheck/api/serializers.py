"""Modellarni JSON ga o'girish."""
from ..core.auth import Perm, can
from ..core.models import Document, Finding, Project, Rule, User
from ..review.engine import source_text
from ..review.messages import PARAM_NAMES, render
from .errors import PARSE_MESSAGES, localize


def user_out(u: User) -> dict:
    return {"id": u.id, "login": u.login, "role": str(u.role), "locale": u.locale,
            "is_active": u.is_active, "permissions": [p.value for p in Perm if can(u.role, p)]}


def project_out(p: Project) -> dict:
    return {"id": p.id, "name": p.name, "industry": p.industry, "stage": str(p.stage),
            "created_at": p.created_at.isoformat(), "allow_cloud_ai": bool(p.allow_cloud_ai)}


def parse_message(d: Document, locale: str) -> str | None:
    status = str(d.parse_status)
    if status in ("parsed", "pending"):
        return None
    code = d.parse_error if d.parse_error in PARSE_MESSAGES else (status if status in PARSE_MESSAGES else "error")
    return localize(PARSE_MESSAGES, code, locale)


def document_out(d: Document, locale: str, active: set[int] | None = None) -> dict:
    """active — tekshiruvda qatnashadigan hujjatlar; berilsa, eskirgan reviziya belgilanadi."""
    return {"superseded": (active is not None and str(d.parse_status) == "parsed" and d.id not in active),
            "id": d.id, "project_id": d.project_id, "filename": d.filename,
            "doc_type": str(d.doc_type), "discipline": str(d.discipline),
            "doc_number": d.doc_number, "revision": d.revision, "sha256": d.sha256,
            "parse_status": str(d.parse_status), "parse_error": d.parse_error,
            "parse_message": parse_message(d, locale), "uploaded_at": d.uploaded_at.isoformat()}


def param_name(param: str | None, locale: str) -> str | None:
    if param is None:
        return None
    return PARAM_NAMES.get(locale, PARAM_NAMES["uz"]).get(param, param)


def rule_title(rule: Rule, locale: str) -> str:
    return {"uz": rule.title_uz, "en": rule.title_en, "ru": rule.title_ru}.get(locale, rule.title_uz)


def rule_out(rule: Rule, locale: str) -> dict:
    return {"code": rule.code, "title": rule_title(rule, locale), "severity": str(rule.severity),
            "enabled": rule.enabled, "source": source_text(rule, locale)}


def finding_out(f: Finding, locale: str, detail: bool = False, users: dict[int, str] | None = None) -> dict:
    description, rationale, recommendation = render(f.description_key, f.args, locale)
    out = {"id": f.id, "run_id": f.run_id, "rule": f.rule.code, "rule_title": rule_title(f.rule, locale),
           "tag": f.tag_text, "param": f.param, "param_name": param_name(f.param, locale),
           "severity": str(f.severity), "confidence": str(f.confidence), "status": str(f.status),
           "source_type": f.source_type, "description": description,
           "documents": sorted({e.document.doc_number or e.document.filename for e in f.evidence})}
    if detail:
        users = users or {}
        out.update({
            "rationale": rationale, "recommendation": recommendation,
            "source": source_text(f.rule, locale),
            "evidence": [{"document_id": e.document_id, "doc_number": e.document.doc_number,
                          "filename": e.document.filename, "doc_type": str(e.document.doc_type),
                          "revision": e.document.revision, "page_no": e.page_no,
                          "location": e.location, "value": e.value} for e in f.evidence],
            "actions": [{"action": a.action, "comment": a.comment, "user": users.get(a.user_id),
                         "created_at": a.created_at.isoformat()} for a in f.actions]})
    return out


def ai_note_out(n, users: dict[int, str] | None = None) -> dict:
    users = users or {}
    return {"id": n.id, "finding_id": n.finding_id, "provider": n.provider_name, "model": n.model,
            "ai_mode": n.ai_mode, "locale": n.locale, "text": n.text, "assumptions": n.assumptions or [],
            "citations": n.citations or [], "status": n.status, "created_by": users.get(n.created_by),
            "decided_by": users.get(n.decided_by), "created_at": n.created_at.isoformat()}


def kb_source_out(s, users: dict[int, str] | None = None) -> dict:
    users = users or {}
    return {"id": s.id, "title": s.title, "kind": s.kind, "standard_code": s.standard_code, "edition": s.edition,
            "status": s.status, "license_type": s.license_type, "filename": s.filename, "approved": s.approved,
            "origin_finding_id": s.origin_finding_id, "added_by": users.get(s.added_by),
            "added_at": s.added_at.isoformat(), "chunks": len(s.chunks)}


def run_out(run, locale: str) -> dict:
    from .errors import ai_reason
    return {"id": run.id, "started_at": run.started_at.isoformat(), "ai_mode": run.ai_mode,
            "ai_provider": run.ai_provider, "ai_note": run.ai_note, "ai_message": ai_reason(run.ai_note, locale),
            "ai_stats": run.ai_stats, "errors": run.errors}
