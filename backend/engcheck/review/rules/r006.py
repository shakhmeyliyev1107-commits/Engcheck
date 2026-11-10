"""R006: hujjat boshqa hujjatning eskirgan reviziyasiga havola qiladi."""
from ...core.models import Confidence, DocRef, Document, ParseStatus, Severity
from .base import Draft, Evidence, RuleBase, doc_label, parsed_docs


class R006(RuleBase):
    code = "R006"

    def check(self, db, project_id):
        current: dict[str, Document] = {}
        for d in parsed_docs(db, project_id):  # id bo'yicha: keyin yuklangani joriy hisoblanadi
            if d.doc_number and d.revision:
                current[d.doc_number.upper()] = d
        refs = (db.query(DocRef).join(Document, DocRef.document_id == Document.id)
                .filter(Document.project_id == project_id,
                        Document.parse_status == ParseStatus.parsed).order_by(DocRef.id).all())
        drafts, seen = [], set()
        for ref in refs:
            target = current.get(ref.ref_doc_number.upper())
            if target is None or target.id == ref.document_id:
                continue
            if (ref.document.doc_number or "").upper() == ref.ref_doc_number.upper():
                continue
            if target.revision.upper() == ref.ref_revision.upper():
                continue
            key = (ref.document_id, ref.ref_doc_number.upper(), ref.ref_revision.upper())
            if key in seen:
                continue
            seen.add(key)
            drafts.append(Draft(
                self.code, None, None, None, Severity.minor, Confidence.medium, "r006_stale_revision",
                {"doc": doc_label(ref.document), "ref_doc": ref.ref_doc_number,
                 "ref_rev": ref.ref_revision, "current_rev": target.revision},
                [Evidence(ref.document_id, ref.page_no, "text",
                          f"{ref.ref_doc_number} Rev {ref.ref_revision}")]))
        return drafts
