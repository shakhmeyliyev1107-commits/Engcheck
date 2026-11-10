"""Tekshiruv seansi: qoidalarni ishga tushiradi va topilmalarni yozadi."""
import hashlib

from sqlalchemy.orm import Session as Db

from ..core import audit
from ..core.models import (Document, Finding, FindingAction, FindingEvidence, FindingStatus,
                           ReviewRun, Rule)
from .messages import INTERNAL_SOURCE, RULE_TITLES, render
from .rules import ALL_RULES, Draft

DEFAULT_SEVERITY = {"R001": "major", "R002": "major", "R003": "minor", "R004": "critical",
                    "R005": "major", "R006": "minor", "R007": "minor"}
CARRIED_STATUSES = (FindingStatus.confirmed, FindingStatus.rejected, FindingStatus.fixed)


def seed_rules(db: Db) -> None:
    """`rules` jadvalini to'ldiradi; mavjud yozuvlarga (enabled, standart) tegmaydi."""
    existing = {r.code for r in db.query(Rule)}
    for rule in ALL_RULES:
        if rule.code not in existing:
            uz, en, ru = RULE_TITLES[rule.code]
            db.add(Rule(code=rule.code, title_uz=uz, title_en=en, title_ru=ru,
                        severity=DEFAULT_SEVERITY[rule.code]))
    db.flush()


def source_text(rule: Rule, locale: str) -> str:
    """Topilma manbasi: faqat amaldagi standartga havola beriladi."""
    std = rule.standard
    if std is not None and std.status == "active":
        return f"{std.code} ({std.edition})" if std.edition else std.code
    return INTERNAL_SOURCE.get(locale, INTERNAL_SOURCE["uz"])


def _fingerprint(db: Db, draft: Draft) -> str:
    pairs = []
    for e in draft.evidence:
        doc = db.get(Document, e.document_id)
        pairs.append(f"{doc.doc_number or doc.filename}={e.value}")
    key = "|".join([draft.rule_code, draft.tag_text or "", draft.param or "",
                    draft.description_key, *sorted(pairs)])
    return hashlib.sha256(key.encode()).hexdigest()


def _carry_decision(db: Db, project_id: int, run_id: int, finding: Finding) -> None:
    previous = (db.query(Finding).join(ReviewRun, Finding.run_id == ReviewRun.id)
                .filter(ReviewRun.project_id == project_id, Finding.run_id != run_id,
                        Finding.fingerprint == finding.fingerprint)
                .order_by(Finding.id.desc()).first())
    if previous is None or previous.status not in CARRIED_STATUSES:
        return
    # "Tuzatilgan" deb belgilangan muammo yana topilsa, u tuzatilmagan: tasdiqlangan holatga qaytadi.
    finding.status = (FindingStatus.confirmed if previous.status == FindingStatus.fixed
                      else previous.status)
    last = previous.actions[-1] if previous.actions else None
    finding.actions.append(FindingAction(user_id=last.user_id if last else None,
                                         action="carried_over",
                                         comment=last.comment if last else ""))


def run_review(db: Db, project_id: int, user_id: int | None) -> ReviewRun:
    seed_rules(db)
    rules = {r.code: r for r in db.query(Rule)}
    run = ReviewRun(project_id=project_id, started_by=user_id, ai_mode="none", errors=[])
    db.add(run)
    db.flush()
    errors, count = [], 0
    for impl in ALL_RULES:
        rule = rules[impl.code]
        if not rule.enabled:
            continue
        try:
            drafts = impl.check(db, project_id)
        except Exception as exc:  # bitta qoidadagi xato seansni to'xtatmasin
            errors.append({"rule": impl.code, "error": f"{type(exc).__name__}: {exc}"})
            continue
        for draft in drafts:
            description, rationale, recommendation = render(draft.description_key, draft.args, "uz")
            finding = Finding(
                run_id=run.id, rule_id=rule.id, tag_id=draft.tag_id, tag_text=draft.tag_text,
                param=draft.param, description_key=draft.description_key, args=draft.args,
                description=description, rationale=rationale, recommendation=recommendation,
                severity=draft.severity, source_type="rule", confidence=draft.confidence,
                status=FindingStatus.new, fingerprint=_fingerprint(db, draft),
                evidence=[FindingEvidence(document_id=e.document_id, page_no=e.page_no,
                                          location=e.location, value=e.value[:255])
                          for e in draft.evidence])
            db.add(finding)
            db.flush()
            _carry_decision(db, project_id, run.id, finding)
            count += 1
    run.errors = errors
    db.flush()
    audit.record(db, user_id, "review.run", "review_run", run.id,
                 {"project_id": project_id, "findings": count, "rule_errors": len(errors)})
    return run
