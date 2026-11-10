"""R001: bir teg va parametr turli hujjatlarda turli qiymatga ega."""
import re
from collections import defaultdict

from ...core.models import Confidence, Severity
from ...ingest.units import PARAM_KIND
from .base import Draft, RuleBase, all_cell_high, param_evidence, project_params, values_text

REL_TOLERANCE = 0.01


def _norm_text(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


class R001(RuleBase):
    code = "R001"

    def check(self, db, project_id):
        groups = defaultdict(list)
        for p in project_params(db, project_id):
            groups[(p.tag_id, p.param)].append(p)
        drafts = []
        for (tag_id, param), items in groups.items():
            if PARAM_KIND.get(param, "text") == "text":
                usable = [p for p in items if p.raw_value.strip()]
                per_doc = defaultdict(set)
                for p in usable:
                    per_doc[p.document_id].add(_norm_text(p.raw_value))
                differs = _cross_doc_text(per_doc)
            else:
                usable = [p for p in items if p.si_value is not None]
                differs = _cross_doc_numeric(usable)
            if not differs:
                continue
            critical = param.endswith(("_pressure", "_temperature"))
            drafts.append(Draft(
                self.code, tag_id, usable[0].tag.tag, param,
                Severity.critical if critical else Severity.major,
                Confidence.high if all_cell_high(usable) else Confidence.medium,
                "r001_mismatch",
                {"tag": usable[0].tag.tag, "param": param, "values": values_text(usable)},
                [param_evidence(p) for p in usable]))
        return drafts


def _cross_doc_numeric(params) -> bool:
    """Farq aynan turli hujjatlar orasida bo'lsagina True."""
    for a in params:
        for b in params:
            if a.document_id != b.document_id and abs(a.si_value - b.si_value) > REL_TOLERANCE * max(
                    abs(a.si_value), abs(b.si_value)):
                return True
    return False


def _cross_doc_text(per_doc: dict[int, set[str]]) -> bool:
    docs = list(per_doc.values())
    return any(a != b for i, a in enumerate(docs) for b in docs[i + 1:])
