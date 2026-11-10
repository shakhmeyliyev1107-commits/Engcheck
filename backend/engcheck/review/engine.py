"""Tekshiruv seansi: qoidalarni ishga tushiradi va topilmalarni yozadi."""
import hashlib

from sqlalchemy.orm import Session as Db

from ..core import audit
from ..core.models import (Document, Finding, FindingAction, FindingEvidence, FindingStatus,
                           ReviewRun, Rule)
from .messages import AI_SOURCE, INTERNAL_SOURCE, RULE_TITLES, render
from .rules import ALL_RULES, Draft

DEFAULT_SEVERITY = {"R001": "major", "R002": "major", "R003": "minor", "R004": "critical",
                    "R005": "major", "R006": "minor", "R007": "minor", "AI01": "minor"}
AI_RULE = "AI01"
CARRIED_STATUSES = (FindingStatus.confirmed, FindingStatus.rejected, FindingStatus.fixed)


def seed_rules(db: Db) -> None:
    """`rules` jadvalini to'ldiradi; mavjud yozuvlarga (enabled, standart) tegmaydi."""
    existing = {r.code for r in db.query(Rule)}
    for code in [rule.code for rule in ALL_RULES] + [AI_RULE]:
        if code not in existing:
            uz, en, ru = RULE_TITLES[code]
            db.add(Rule(code=code, title_uz=uz, title_en=en, title_ru=ru, severity=DEFAULT_SEVERITY[code]))
    db.flush()


def source_text(rule: Rule, locale: str) -> str:
    """Topilma manbasi: faqat amaldagi standartga havola beriladi."""
    if rule.code == AI_RULE:
        return AI_SOURCE.get(locale, AI_SOURCE["uz"])
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


def _store(db: Db, run: ReviewRun, rule: Rule, draft: Draft, project_id: int, locale: str) -> None:
    description, rationale, recommendation = render(draft.description_key, draft.args, locale)
    finding = Finding(
        run_id=run.id, rule_id=rule.id, tag_id=draft.tag_id, tag_text=draft.tag_text,
        param=draft.param, description_key=draft.description_key, args=draft.args,
        description=description, rationale=rationale, recommendation=recommendation,
        severity=draft.severity, source_type="ai" if rule.code == AI_RULE else "rule",
        confidence=draft.confidence, status=FindingStatus.new, fingerprint=_fingerprint(db, draft),
        evidence=[FindingEvidence(document_id=e.document_id, page_no=e.page_no,
                                  location=e.location, value=e.value[:255])
                  for e in draft.evidence])
    db.add(finding)
    db.flush()
    _carry_decision(db, project_id, run.id, finding)


def run_review(db: Db, project_id: int, user_id: int | None, resolution=None, locale: str = "uz") -> ReviewRun:
    """Qoidalarni ishga tushiradi; `resolution` berilsa, AI tekshiruvini ham.

    resolution — ai.registry.resolve() natijasi. AI topilmalari alohida belgilanadi
    (source_type="ai", ishonchlilik low) va qoida topilmalariga ta'sir qilmaydi.
    """
    from ..ai.base import AiError
    from ..ai.review import ai_findings

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
            _store(db, run, rule, draft, project_id, "uz")
            count += 1

    if resolution is not None:
        if not rules[AI_RULE].enabled:
            run.ai_note = "rule_disabled"
        elif resolution.provider is None:
            run.ai_note = resolution.reason or "no_provider"
        else:
            run.ai_mode, run.ai_provider = resolution.mode, resolution.provider.name
            try:
                drafts, stats = ai_findings(db, project_id, resolution.provider, locale)
            except AiError as exc:   # provayder o'chsa, qoida topilmalari saqlanib qoladi
                errors.append({"rule": AI_RULE, "error": exc.code})
            else:
                run.ai_stats = stats
                for draft in drafts:
                    _store(db, run, rules[AI_RULE], draft, project_id, locale)
                    count += 1
    run.errors = errors
    db.flush()
    audit.record(db, user_id, "review.run", "review_run", run.id,
                 {"project_id": project_id, "findings": count, "rule_errors": len(errors),
                  "ai_mode": run.ai_mode, "ai_provider": run.ai_provider})
    return run
