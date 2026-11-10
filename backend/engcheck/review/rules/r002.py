"""R002: teg bir hujjat turida bor, kutilgan boshqasida yo'q."""
from collections import defaultdict

from ...core.models import Confidence, DocType, Method, Severity, TagClass
from ...ingest.tagging import tag_prefix
from .base import Draft, Evidence, RuleBase, doc_label, parsed_docs, project_occurrences

PID, EQL, LL, DS = DocType.PID, DocType.EQUIPMENT_LIST, DocType.LINE_LIST, DocType.DATASHEET


class R002(RuleBase):
    code = "R002"

    def check(self, db, project_id):
        types_present = {d.doc_type for d in parsed_docs(db, project_id)}
        by_type = defaultdict(lambda: defaultdict(list))  # doc_type -> tag_id -> occurrences
        for occ in project_occurrences(db, project_id):
            by_type[occ.document.doc_type][occ.tag_id].append(occ)

        def rows(doc_type):
            """Hujjatning o'z qatorlari (jadval katagi/blok atributi), matndagi eslatmalar emas."""
            return {tag_id: [o for o in occs if o.method == Method.cell]
                    for tag_id, occs in by_type[doc_type].items()
                    if any(o.method == Method.cell for o in occs)}

        # Loyihada uskuna sifatida ishlatilgan prefikslar (ro'yxat va datasheetlardan).
        prefixes = {tag_prefix(occs[0].tag.tag) for dt in (EQL, DS) for occs in rows(dt).values()
                    if occs[0].tag.tag_class == TagClass.equipment}
        drafts = []

        def missing(occs, present_in, missing_in):
            tag = occs[0].tag
            cell = any(o.method == Method.cell for o in occs)
            drafts.append(Draft(
                self.code, tag.id, tag.tag, None, Severity.major,
                Confidence.high if cell else Confidence.medium, "r002_missing",
                {"tag": tag.tag, "present_in": str(present_in), "missing_in": str(missing_in),
                 "docs": ", ".join(sorted({doc_label(o.document) for o in occs}))},
                [Evidence(o.document_id, o.page_no, o.location, tag.tag) for o in occs]))

        if PID in types_present and EQL in types_present:
            for tag_id, occs in by_type[PID].items():
                tag = occs[0].tag
                if tag.tag_class == TagClass.line or tag_id in by_type[EQL]:
                    continue
                cell = any(o.method == Method.cell for o in occs)
                # Matndan topilgan teg faqat prefiksi loyihada uskuna sifatida ma'lum bo'lsa tekshiriladi:
                # aks holda "API-610", "XV-1001" kabi yozuvlar soxta topilma beradi.
                if (cell and tag.tag_class == TagClass.equipment) or tag_prefix(tag.tag) in prefixes:
                    missing(occs, PID, EQL)
            for tag_id, occs in rows(EQL).items():
                if occs[0].tag.tag_class != TagClass.line and tag_id not in by_type[PID]:
                    missing(occs, EQL, PID)
        if PID in types_present and LL in types_present:
            for present_in, missing_in in ((PID, LL), (LL, PID)):
                for tag_id, occs in by_type[present_in].items():
                    if occs[0].tag.tag_class == TagClass.line and tag_id not in by_type[missing_in]:
                        missing(occs, present_in, missing_in)
        if DS in types_present and EQL in types_present:
            for tag_id, occs in rows(DS).items():
                if occs[0].tag.tag_class != TagClass.line and tag_id not in by_type[EQL]:
                    missing(occs, DS, EQL)
        return drafts
