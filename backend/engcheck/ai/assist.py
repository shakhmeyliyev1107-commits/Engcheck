"""Topilmaga AI izohi: bilimlar bazasidagi manbalarga tayangan, tasdiqlanmagan tushuntirish."""
import json
import re

from sqlalchemy.orm import Session as Db

from ..core import audit
from ..core.models import Finding, FindingAiNote, User
from ..kb.service import Hit, prompt_text, search
from ..review.messages import render
from .base import AiError
from .registry import Resolution

LANGUAGE = {"uz": "Uzbek", "en": "English", "ru": "Russian"}
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_MARKER = re.compile(r"\s*\[(K\d+)\]")

SYSTEM = """You are assisting a process-plant design engineer who reviews engineering documents.
You are given one review finding (facts read from project documents) and numbered excerpts [K1], [K2]... \
from the engineer's own knowledge base.

Rules:
- Explain the technical significance of the finding and what the engineer should check.
- Use only the facts given. Do not invent values, clauses, document numbers or standards.
- When a statement relies on a knowledge-base excerpt, cite it inline as [K1]. Cite only excerpts you were given. \
If none is relevant, say so plainly and cite nothing.
- Some excerpts have their text withheld (licensed); you may point the engineer to them by reference only.
- An excerpt marked superseded comes from a replaced edition: mention that if you rely on it.
- Anything that is your inference rather than a given fact goes into "assumptions".
- Write in {language}. You do not approve or reject the finding; the engineer decides.

Reply with JSON only: {{"explanation": "...", "citations": ["K1"], "assumptions": ["..."]}}"""


class AssistError(Exception):
    """code: provayder topilmagan sabab (no_provider, cloud_not_allowed, ...), AiError kodi yoki bad_response"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def extract_json(text: str):
    """Javobdan JSON ni ajratib oladi: ```json bloki yoki matn ichidagi birinchi obyekt/massiv."""
    text = (text or "").strip()
    fenced = _FENCE.search(text)
    candidates = [fenced.group(1).strip()] if fenced else []
    candidates.append(text)
    decoder = json.JSONDecoder()
    for candidate in candidates:
        for match in re.finditer(r"[{\[]", candidate):
            try:
                value, _ = decoder.raw_decode(candidate[match.start():])
                return value
            except ValueError:
                continue
    return None


def _kb_block(hits: list[Hit], for_cloud: bool) -> str:
    if not hits:
        return "(the knowledge base returned nothing relevant)"
    lines = []
    for i, hit in enumerate(hits, start=1):
        ref = " — ".join(x for x in (hit.title, hit.standard_code, hit.edition) if x)
        status = "" if hit.status == "active" else f" ({hit.status})"
        text = prompt_text(hit, for_cloud)
        body = text if text is not None else "(text withheld: not cleared for this provider; cite by reference only)"
        lines.append(f"[K{i}] {ref}{status}, p.{hit.page_no}:\n{body}")
    return "\n\n".join(lines)


def explain_finding(db: Db, finding: Finding, user: User | None, locale: str,
                    resolution: Resolution) -> FindingAiNote:
    provider = resolution.provider
    if provider is None:
        raise AssistError(resolution.reason or "no_provider")
    description, rationale, recommendation = render(finding.description_key, finding.args, "en")
    hits = search(db, f"{description} {rationale}", k=5, provider=provider)
    evidence = "\n".join(
        f"- {e.document.doc_number or e.document.filename} ({e.document.doc_type}, Rev {e.document.revision or '-'}), "
        f"page {e.page_no}: {e.value}" for e in finding.evidence)
    user_prompt = (f"FINDING ({finding.rule.code}, severity {finding.severity}, confidence {finding.confidence})\n"
                   f"{description}\n{rationale}\nRecommended correction: {recommendation}\n\n"
                   f"EVIDENCE READ FROM DOCUMENTS\n{evidence}\n\n"
                   f"KNOWLEDGE BASE EXCERPTS\n{_kb_block(hits, for_cloud=not provider.is_local)}")
    try:
        result = provider.chat(SYSTEM.format(language=LANGUAGE.get(locale, "Uzbek")), user_prompt)
    except AiError as exc:
        raise AssistError(exc.code) from exc
    except Exception as exc:   # provayder kutilmagan shakldagi javob qaytarsa ham 500 emas
        raise AssistError("server") from exc
    data = extract_json(result.text)
    if not isinstance(data, dict) or not isinstance(data.get("explanation"), str) or not data["explanation"].strip():
        raise AssistError("bad_response")

    provided = {f"K{i}": hit for i, hit in enumerate(hits, start=1)}
    listed = data.get("citations") if isinstance(data.get("citations"), list) else []
    inline = _MARKER.findall(data["explanation"])   # matn ichidagi [K1] ham havola hisoblanadi
    cited = [key for key in dict.fromkeys([str(c) for c in listed] + inline) if key in provided]
    # Berilmagan manbaga ishora matndan olib tashlanadi: uydirma havola ko'rsatilmaydi.
    text = _MARKER.sub(lambda m: m.group(0) if m.group(1) in provided else "", data["explanation"]).strip()
    citations = [{"key": key, "source_id": h.source_id, "chunk_id": h.chunk_id, "title": h.title,
                  "standard_code": h.standard_code, "edition": h.edition, "status": h.status,
                  "license_type": h.license_type, "page_no": h.page_no, "excerpt": h.excerpt}
                 for key, h in ((k, provided[k]) for k in cited)]
    raw = data.get("assumptions") if isinstance(data.get("assumptions"), list) else []
    assumptions = [str(a).strip() for a in raw if isinstance(a, (str, int, float)) and str(a).strip()][:10]
    note = FindingAiNote(finding_id=finding.id, provider_name=provider.name, model=result.model,
                         ai_mode=resolution.mode, locale=locale, text=text, assumptions=assumptions,
                         citations=citations, status="proposed", created_by=user.id if user else None)
    db.add(note)
    db.flush()
    audit.record(db, user.id if user else None, "ai.note", "ai_note", note.id,
                 {"finding_id": finding.id, "provider": provider.name, "mode": resolution.mode})
    return note
