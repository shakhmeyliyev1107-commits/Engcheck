"""R002: teg bir hujjat turida bor, kutilgan boshqasida yo'q."""
from collections import defaultdict

from ...core.models import Confidence, DocType, Method, Severity, TagClass
from .base import Draft, Evidence, RuleBase, doc_label, parsed_docs, project_occurrences

# (teg sinfi, mavjud bo'lgan tur, bo'lishi kutilgan tur)
EXPECTATIONS = [
    (TagClass.equipment, DocType.PID, DocType.EQUIPMENT_LIST),
    (TagClass.equipment, DocType.EQUIPMENT_LIST, DocType.PID),
    (TagClass.line, DocType.PID, DocType.LINE_LIST),
    (TagClass.line, DocType.LINE_LIST, DocType.PID),
    (TagClass.equipment, DocType.DATASHEET, DocType.EQUIPMENT_LIST),
]


class R002(RuleBase):
    code = "R002"

    def check(self, db, project_id):
        types_present = {d.doc_type for d in parsed_docs(db, project_id)}
        by_type = defaultdict(lambda: defaultdict(list))  # doc_type -> tag_id -> occurrences
        for occ in project_occurrences(db, project_id):
            by_type[occ.document.doc_type][occ.tag_id].append(occ)
        drafts = []
        for tag_class, present_in, missing_in in EXPECTATIONS:
            if present_in not in types_present or missing_in not in types_present:
                continue
            for tag_id, occs in by_type[present_in].items():
                tag = occs[0].tag
                if tag.tag_class != tag_class or tag_id in by_type[missing_in]:
                    continue
                cell = any(o.method == Method.cell for o in occs)
                drafts.append(Draft(
                    self.code, tag_id, tag.tag, None, Severity.major,
                    Confidence.high if cell else Confidence.medium, "r002_missing",
                    {"tag": tag.tag, "present_in": str(present_in), "missing_in": str(missing_in),
                     "docs": ", ".join(sorted({doc_label(o.document) for o in occs}))},
                    [Evidence(o.document_id, o.page_no, o.location, tag.tag) for o in occs]))
        return drafts
