"""R005: line listdagi quvur sinfi material spetsifikatsiyasida yo'q."""
from collections import defaultdict

from ...core.models import Confidence, DocType, Severity, TagClass
from .base import Draft, Evidence, RuleBase, doc_label, parsed_docs, project_occurrences, project_params


class R005(RuleBase):
    code = "R005"

    def check(self, db, project_id):
        specs = parsed_docs(db, project_id, DocType.MATERIAL_SPEC)
        if not specs:
            return []
        defined = {o.tag.tag.upper() for o in project_occurrences(db, project_id)
                   if o.tag.tag_class == TagClass.pipe_class
                   and o.document.doc_type == DocType.MATERIAL_SPEC}
        used = defaultdict(list)
        for p in project_params(db, project_id):
            if p.param == "pipe_class" and p.document.doc_type == DocType.LINE_LIST:
                used[p.raw_value.strip().upper()].append(p)
        drafts = []
        for pipe_class, params in used.items():
            if pipe_class in defined:
                continue
            drafts.append(Draft(
                self.code, None, pipe_class, "pipe_class", Severity.major, Confidence.high,
                "r005_class_undefined",
                {"pipe_class": pipe_class, "lines": ", ".join(p.tag.tag for p in params),
                 "spec": ", ".join(doc_label(d) for d in specs)},
                [Evidence(p.document_id, p.page_no, p.location, f"{p.tag.tag}: {p.raw_value}")
                 for p in params]))
        return drafts
