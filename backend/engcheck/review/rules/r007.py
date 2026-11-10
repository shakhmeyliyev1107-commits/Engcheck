"""R007: sonli qiymatning birligi tanilmadi."""
from ...core.models import Confidence, Severity
from .base import Draft, RuleBase, doc_label, param_evidence, project_params


class R007(RuleBase):
    code = "R007"

    def check(self, db, project_id):
        return [Draft(self.code, p.tag_id, p.tag.tag, p.param, Severity.minor, Confidence.high,
                      "r007_unknown_unit",
                      {"tag": p.tag.tag, "param": p.param, "value": p.raw_value,
                       "doc": doc_label(p.document)}, [param_evidence(p)])
                for p in project_params(db, project_id)
                if p.number is not None and p.si_value is None and not p.unit_known]
