"""R006: hujjat boshqa hujjatning loyihadagidan farqli reviziyasiga havola qiladi."""
from ...core.models import Confidence, DocRef, Document, Severity
from .base import (Draft, Evidence, RuleBase, active_docs, doc_label, revision_rank, same_revision)


class R006(RuleBase):
    code = "R006"

    def check(self, db, project_id):
        docs = active_docs(db, project_id)
        current = {d.doc_number.upper(): d for d in docs if d.doc_number and d.revision}
        refs = (db.query(DocRef).filter(DocRef.document_id.in_([d.id for d in docs]))
                .order_by(DocRef.id).all())
        drafts, seen = [], set()
        for ref in refs:
            number = ref.ref_doc_number.upper()
            target = current.get(number)
            if target is None or (ref.document.doc_number or "").upper() == number:
                continue
            if same_revision(target.revision, ref.ref_revision):
                continue
            key = (ref.document_id, number, ref.ref_revision.upper())
            if key in seen:
                continue
            seen.add(key)
            older = revision_rank(ref.ref_revision) < revision_rank(target.revision)
            drafts.append(Draft(
                self.code, None, None, None, Severity.minor, Confidence.medium,
                "r006_stale_revision" if older else "r006_newer_revision",
                {"doc": doc_label(ref.document), "ref_doc": ref.ref_doc_number,
                 "ref_rev": ref.ref_revision, "current_rev": target.revision},
                [Evidence(ref.document_id, ref.page_no, "text",
                          f"{ref.ref_doc_number} Rev {ref.ref_revision}")]))
        return drafts
