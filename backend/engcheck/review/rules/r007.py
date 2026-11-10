"""R007: sonli qiymat solishtirib bo'lmaydigan ko'rinishda (birlik tanilmadi yoki qiymat o'qilmadi)."""
from ...core.models import Confidence, Severity
from ...ingest.units import PARAM_KIND, is_placeholder
from .base import Draft, RuleBase, doc_label, param_evidence, project_params


class R007(RuleBase):
    code = "R007"

    def check(self, db, project_id):
        drafts = []
        for p in project_params(db, project_id):
            if PARAM_KIND.get(p.param, "text") == "text" or p.si_value is not None:
                continue
            if p.number is not None and not p.unit_known:
                key, severity = "r007_unknown_unit", Severity.minor
            elif p.number is None and p.raw_value.strip() and not is_placeholder(p.raw_value):
                key, severity = "r007_unparsed_value", Severity.info   # diapazon, noaniq yozuv va h.k.
            else:
                continue
            drafts.append(Draft(self.code, p.tag_id, p.tag.tag, p.param, severity, Confidence.high, key,
                                {"tag": p.tag.tag, "param": p.param, "value": p.raw_value,
                                 "doc": doc_label(p.document)}, [param_evidence(p)]))
        return drafts
