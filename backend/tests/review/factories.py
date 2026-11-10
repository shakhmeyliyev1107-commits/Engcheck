"""Qoida testlari uchun bazaga to'g'ridan-to'g'ri yozadigan yordamchilar."""
import itertools

from engcheck.core.models import (Confidence, Discipline, DocRef, DocType, Document, Method,
                                  ParseStatus, Tag, TagClass, TagOccurrence, TagParam)
from engcheck.ingest.tagging import classify

_seq = itertools.count(1)


def make_doc(db, project, doc_type, number=None, rev="A"):
    n = next(_seq)
    d = Document(project_id=project.id, filename=f"{number or 'doc'}-{n}.x", doc_type=doc_type,
                 discipline=Discipline.process, doc_number=number or f"XX-DOC-{n:03d}", revision=rev,
                 sha256=f"{n:064d}", parse_status=ParseStatus.parsed)
    db.add(d)
    db.flush()
    return d


def make_tag(db, project, doc, tag, tag_class=None, method=Method.cell, page=1):
    row = db.query(Tag).filter_by(project_id=project.id, tag=tag).first()
    if row is None:
        row = Tag(project_id=project.id, tag=tag, tag_class=tag_class or classify(tag))
        db.add(row)
        db.flush()
    if not db.query(TagOccurrence).filter_by(tag_id=row.id, document_id=doc.id).first():
        db.add(TagOccurrence(tag_id=row.id, document_id=doc.id, page_no=page, location="A1", method=method))
        db.flush()
    return row


def make_param(db, project, doc, tag, param, raw, si=None, method=Method.cell,
               confidence=Confidence.high, number=None, unit_known=True, page=1):
    row = make_tag(db, project, doc, tag, method=method, page=page)
    p = TagParam(tag_id=row.id, param=param, raw_value=raw, si_value=si,
                 number=number if number is not None else si, unit_known=unit_known,
                 document_id=doc.id, page_no=page, location="B2", method=method, confidence=confidence)
    db.add(p)
    db.flush()
    return p


def make_ref(db, doc, number, rev, page=1):
    db.add(DocRef(document_id=doc.id, ref_doc_number=number, ref_revision=rev, page_no=page))
    db.flush()


PID, EQL, LL, DS, MS = (DocType.PID, DocType.EQUIPMENT_LIST, DocType.LINE_LIST, DocType.DATASHEET,
                        DocType.MATERIAL_SPEC)
PIPE_CLASS = TagClass.pipe_class
