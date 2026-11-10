"""Hujjat matnidan AI topilmalari. Har biri hujjatdan so'zma-so'z iqtibosga tayanishi shart."""
import re

from sqlalchemy.orm import Session as Db

from ..core.models import Confidence, DocPage, Severity, Tag
from ..ingest.tagging import find_tags
from ..review.rules.base import Draft, Evidence, active_docs
from .assist import LANGUAGE, extract_json
from .base import AiError, Provider

MAX_PAGES = 40          # bitta tekshiruvda AI ko'radigan sahifalar soni
MAX_PAGE_CHARS = 12000  # bitta sahifadan yuboriladigan matn
MIN_QUOTE = 12
MIN_TOKENS = 3   # iqtibosda kamida shuncha so'z/son bo'lishi kerak
_SEVERITIES = {s.value for s in Severity}

SYSTEM = """You review one page of an engineering document from a process-plant design project \
(document type: {doc_type}). Report only issues that are visible in the text itself: internal contradictions, \
physically implausible values, missing units, undefined references, obvious omissions.

Rules:
- Every issue must include "quote": a fragment copied character-for-character from the page (12–200 characters) \
that shows the issue. If you cannot quote it, do not report it.
- Do not guess about content that is not on the page. Do not cite standards.
- "severity" is one of: critical, major, minor, info.
- Write "issue" and "recommendation" in {language}.

Reply with a JSON array only: [{{"quote": "...", "issue": "...", "recommendation": "...", "severity": "minor"}}]
Reply [] if there is nothing to report."""


def _normalise(text: str) -> tuple[str, list[int]]:
    """Solishtirish uchun matn: kichik harf, ketma-ket bo'shliqlar bitta. Har belgi asl matndagi o'rni bilan."""
    out, index, space = [], [], True
    for i, ch in enumerate(text or ""):
        if ch.isspace():
            if not space:
                out.append(" "); index.append(i)
            space = True
        else:
            low = ch.lower()
            out.append(low if len(low) == 1 else ch); index.append(i)
            space = False
    while out and out[-1] == " ":
        out.pop(); index.pop()
    return "".join(out), index


def _find_quote(page_text: str, quote: str) -> str | None:
    """Iqtibos sahifada bo'lsa, uning HUJJATDAGI asl ko'rinishini qaytaradi; bo'lmasa None."""
    needle, _ = _normalise(quote)
    if len(needle) < MIN_QUOTE or len(re.findall(r"[^\W_]{2,}|\d", needle)) < MIN_TOKENS:
        return None
    haystack, index = _normalise(page_text)
    at = haystack.find(needle)
    if at < 0:
        return None
    return page_text[index[at]:index[at + len(needle) - 1] + 1]


def ai_findings(db: Db, project_id: int, provider: Provider, locale: str) -> tuple[list[Draft], dict, str | None]:
    """(topilma qoralamalari, statistika, xato kodi yoki None).

    Provayder o'rtada o'chsa, shu paytgacha topilganlar saqlanadi va xato kodi qaytadi.
    """
    stats = {"pages_reviewed": 0, "pages_skipped": 0, "pages_failed": 0, "pages_truncated": 0, "rejected": 0}
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
            system = SYSTEM.format(doc_type=doc.doc_type, language=LANGUAGE.get(locale, "Uzbek"))
            try:
                reply = provider.chat(system, page.text[:MAX_PAGE_CHARS])
            except AiError as exc:
                return drafts, stats, exc.code
            except Exception:
                return drafts, stats, "server"
            stats["pages_reviewed"] += 1
            if len(page.text) > MAX_PAGE_CHARS:
                stats["pages_truncated"] += 1
            items = extract_json(reply.text)
            if not isinstance(items, list):
                stats["pages_failed"] += 1
                continue
            for item in items:
                quote = item.get("quote") if isinstance(item, dict) else None
                issue = item.get("issue") if isinstance(item, dict) else None
                found_quote = _find_quote(page.text[:MAX_PAGE_CHARS], quote) if isinstance(quote, str) else None
                if found_quote is None or not isinstance(issue, str) or not issue.strip():
                    stats["rejected"] += 1   # iqtibos hujjatda yo'q yoki element yaroqsiz
                    continue
                severity = item.get("severity")
                severity = severity if isinstance(severity, str) and severity in _SEVERITIES else "minor"
                quote = found_quote[:200]
                found = find_tags(quote)
                tag = found[0][0] if found else None
                recommendation = item.get("recommendation")
                drafts.append(Draft(
                    "AI01", tags.get(tag), tag, None, Severity(severity), Confidence.low, "ai_text",
                    {"issue": issue.strip(),
                     "recommendation": recommendation.strip() if isinstance(recommendation, str) and recommendation.strip() else "—",
                     "quote": quote, "doc": doc.doc_number or doc.filename},
                    [Evidence(doc.id, page.page_no, "text", quote)]))
    return drafts, stats, None
