"""R003: majburiy parametr bo'sh."""
from collections import defaultdict

from ...core.models import Confidence, DocType, Severity
from .base import Draft, Evidence, RuleBase, doc_label, project_params

REQUIRED = {
    DocType.DATASHEET: ("design_pressure", "design_temperature", "material"),
    DocType.LINE_LIST: ("size", "fluid", "pipe_class"),
}
# Nasos datasheetida loyiha bosimi/harorati majburiy emas.
PUMP_REQUIRED = ("material",)


class R003(RuleBase):
    code = "R003"

    def check(self, db, project_id):
        rows = defaultdict(list)  # (document_id, tag_id) -> params
        for p in project_params(db, project_id):
            if p.document.doc_type in REQUIRED:
                rows[(p.document_id, p.tag_id)].append(p)
        drafts = []
        for params in rows.values():
            first = params[0]
            required = REQUIRED[first.document.doc_type]
            if first.document.doc_type == DocType.DATASHEET and first.tag.tag.startswith("P-"):
                required = PUMP_REQUIRED
            have = {p.param for p in params}
            for param in required:
                if param in have:
                    continue
                drafts.append(Draft(
                    self.code, first.tag_id, first.tag.tag, param,
                    Severity.major if param.startswith("design_") else Severity.minor,
                    Confidence.high, "r003_missing_param",
                    {"tag": first.tag.tag, "param": param, "doc": doc_label(first.document)},
                    [Evidence(first.document_id, first.page_no, first.location, "—")]))
        return drafts
