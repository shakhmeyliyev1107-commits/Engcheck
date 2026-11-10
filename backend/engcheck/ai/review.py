"""Hujjat matnidan AI topilmalari. Har biri hujjatdan so'zma-so'z iqtibosga tayanishi shart."""
import re

from sqlalchemy.orm import Session as Db

from ..core.models import Confidence, DocPage, Severity, Tag
from ..ingest.tagging import find_tags
from ..review.rules.base import Draft, Evidence, active_docs
from .assist import LANGUAGE, extract_json
from .base import Provider

MAX_PAGES = 40          # bitta tekshiruvda AI ko'radigan sahifalar soni
MAX_PAGE_CHARS = 12000  # bitta sahifadan yuboriladigan matn
MIN_QUOTE = 8
_SEVERITIES = {s.value for s in Severity}

SYSTEM = """You review one page of an engineering document from a process-plant design project \
(document type: {doc_type}). Report only issues that are visible in the text itself: internal contradictions, \
physically implausible values, missing units, undefined references, obvious omissions.

Rules:
- Every issue must include "quote": a fragment copied character-for-character from the page (8–200 characters) \
that shows the issue. If you cannot quote it, do not report it.
- Do not guess about content that is not on the page. Do not cite standards.
- "severity" is one of: critical, major, minor, info.
- Write "issue" and "recommendation" in {language}.

Reply with a JSON array only: [{{"quote": "...", "issue": "...", "recommendation": "...", "severity": "minor"}}]
Reply [] if there is nothing to report."""


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().casefold()


def ai_findings(db: Db, project_id: int, provider: Provider, locale: str) -> tuple[list[Draft], dict]:
    """(topilma qoralamalari, statistika). Provayder xatosi (AiError) yuqoriga uzatiladi."""
    stats = {"pages_reviewed": 0, "pages_skipped": 0, "pages_failed": 0, "rejected": 0}
    drafts: list[Draft] = []
    tags = {t.tag: t.id for t in db.query(Tag).filter_by(project_id=project_id)}
    for doc in active_docs(db, project_id):
        pages = db.query(DocPage).filter_by(document_id=doc.id).order_by(DocPage.page_no).all()
        for page in pages:
            if not page.text.strip():
                continue
            if stats["pages_reviewed"] >= MAX_PAGES:
                stats["pages_skipped"] += 1   # chegaradan oshgan sahifalar sanaladi, jim tashlanmaydi
                continue
            stats["pages_reviewed"] += 1
            system = SYSTEM.format(doc_type=doc.doc_type, language=LANGUAGE.get(locale, "Uzbek"))
            reply = provider.chat(system, page.text[:MAX_PAGE_CHARS])
            items = extract_json(reply.text)
            if not isinstance(items, list):
                stats["pages_failed"] += 1
                continue
            haystack = _norm(page.text)
            for item in items:
                quote = item.get("quote") if isinstance(item, dict) else None
                issue = item.get("issue") if isinstance(item, dict) else None
                if (not isinstance(quote, str) or not isinstance(issue, str) or not issue.strip()
                        or len(_norm(quote)) < MIN_QUOTE or _norm(quote) not in haystack):
                    stats["rejected"] += 1   # iqtibos hujjatda yo'q yoki element yaroqsiz
                    continue
                severity = item.get("severity") if item.get("severity") in _SEVERITIES else "minor"
                found = find_tags(quote)
                tag = found[0][0] if found else None
                quote = quote.strip()[:200]
                drafts.append(Draft(
                    "AI01", tags.get(tag), tag, None, Severity(severity), Confidence.low, "ai_text",
                    {"issue": issue.strip(), "recommendation": str(item.get("recommendation") or "").strip() or "—",
                     "quote": quote, "doc": doc.doc_number or doc.filename},
                    [Evidence(doc.id, page.page_no, "text", quote)]))
    return drafts, stats
