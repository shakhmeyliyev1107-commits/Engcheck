from pathlib import Path

import pytest

from engcheck.core.models import (AuditLog, Discipline, DocPage, DocRef, DocType, Document, Method,
                                  ParseStatus, Tag, TagOccurrence, TagParam)
from engcheck.ingest.service import (DuplicateDocument, delete_document, ingest_file,
                                     suggest_doc_type, suggest_number_revision)


def _ingest(db, settings, project, d):
    return ingest_file(db, settings, project.id, None, d.path, d.path.name, d.doc_type,
                       d.discipline, d.doc_number, d.revision)


def test_ingest_persists_params_with_provenance(db, ingest_sample):
    doc = ingest_sample["GP-DS-V101"]
    assert doc.parse_status == ParseStatus.parsed and doc.parse_error is None
    tag = db.query(Tag).filter_by(tag="V-101").one()
    p = db.query(TagParam).filter_by(tag_id=tag.id, document_id=doc.id, param="design_pressure").one()
    assert p.si_value == 1400.0 and p.raw_value == "14 barg" and p.raw_unit == "barg"
    assert p.page_no == 1 and p.location and p.method == Method.cell
    assert db.query(DocPage).filter_by(document_id=doc.id).count() == 1


def test_original_file_stored_unchanged(db, settings, ingest_sample, sample_docs):
    doc = ingest_sample["GP-PID-001"]
    stored = Path(doc.stored_path)
    assert stored.is_file() and settings.files_dir in stored.parents
    assert stored.read_bytes() == sample_docs[0].path.read_bytes()


def test_same_tag_across_docs_is_one_row(db, ingest_sample):
    tag = db.query(Tag).filter_by(tag="V-101").one()
    docs = {o.document_id for o in db.query(TagOccurrence).filter_by(tag_id=tag.id)}
    assert len(docs) == 4   # P&ID, uskunalar ro'yxati, datasheet va quvurlar ro'yxati (From/To ustunlari)


def test_refs_persisted(db, ingest_sample):
    ref = db.query(DocRef).filter_by(document_id=ingest_sample["GP-DS-V101"].id).one()
    assert (ref.ref_doc_number, ref.ref_revision, ref.page_no) == ("GP-PID-001", "A", 1)


def test_unmapped_headers_saved(db, ingest_sample):
    assert "Description" in ingest_sample["GP-EQL-001"].unmapped_headers


def test_duplicate_rejected(db, settings, project, sample_docs):
    _ingest(db, settings, project, sample_docs[0])
    with pytest.raises(DuplicateDocument):
        _ingest(db, settings, project, sample_docs[0])
    assert db.query(Document).count() == 1


def test_dwg_marked_unsupported_not_raised(db, settings, project, tmp_path):
    p = tmp_path / "plan.dwg"
    p.write_bytes(b"AC1032" + b"\0" * 100)
    doc = ingest_file(db, settings, project.id, None, p, "plan.dwg", DocType.PID, Discipline.process)
    assert doc.parse_status == ParseStatus.unsupported and doc.parse_error == "unsupported_dwg"


def test_scanned_pdf_marked_needs_ocr(db, settings, project, tmp_path):
    from reportlab.pdfgen import canvas
    p = tmp_path / "scan.pdf"
    c = canvas.Canvas(str(p))
    c.rect(10, 10, 50, 50)
    c.save()
    doc = ingest_file(db, settings, project.id, None, p, "scan.pdf", DocType.PFD, Discipline.process)
    assert doc.parse_status == ParseStatus.needs_ocr


def test_corrupt_file_marked_error_and_next_file_still_ingests(db, settings, project, tmp_path, sample_docs):
    bad = tmp_path / "bad.xlsx"
    bad.write_bytes(b"PK\x03\x04 broken")
    doc = ingest_file(db, settings, project.id, None, bad, "bad.xlsx", DocType.LINE_LIST, Discipline.piping)
    assert doc.parse_status == ParseStatus.error and doc.parse_error.startswith("corrupt")
    assert db.query(TagParam).count() == 0
    ok = _ingest(db, settings, project, sample_docs[1])
    assert ok.parse_status == ParseStatus.parsed


def test_upload_is_audited(db, settings, project, sample_docs):
    doc = _ingest(db, settings, project, sample_docs[0])
    row = db.query(AuditLog).one()
    assert (row.action, row.object_type, row.object_id) == ("document.upload", "document", doc.id)
    assert row.details["sha256"] == doc.sha256


def test_number_and_revision_fall_back_to_extracted(db, settings, project, sample_docs):
    d = sample_docs[3]  # GP-DS-V101: hujjat ichida Document No. va Revision bor
    doc = ingest_file(db, settings, project.id, None, d.path, "x.pdf", d.doc_type, d.discipline)
    assert (doc.doc_number, doc.revision) == ("GP-DS-V101", "A")


def test_delete_document_keeps_shared_tags(db, settings, ingest_sample):
    doc = ingest_sample["GP-DS-V101"]
    stored = Path(doc.stored_path)
    delete_document(db, settings, doc.id, None)
    assert db.get(Document, doc.id) is None and not stored.exists()
    assert db.query(TagParam).filter_by(document_id=doc.id).count() == 0
    assert db.query(Tag).filter_by(tag="V-101").count() == 1          # boshqa hujjatlarda bor
    delete_document(db, settings, ingest_sample["GP-MS-001"].id, None)
    assert db.query(Tag).filter_by(tag="B1A").count() == 0             # faqat shu hujjatda edi


@pytest.mark.parametrize("name,expected", [
    ("GP-PID-001_RevC.dxf", DocType.PID), ("P&ID unit 100.pdf", DocType.PID),
    ("GP-EQL-001_RevB.xlsx", DocType.EQUIPMENT_LIST), ("Equipment list.xlsx", DocType.EQUIPMENT_LIST),
    ("GP-LL-001_RevB.xlsx", DocType.LINE_LIST), ("GP-DS-V101_RevA.pdf", DocType.DATASHEET),
    ("GP-MS-001_RevA.docx", DocType.MATERIAL_SPEC), ("PFD-100.pdf", DocType.PFD),
    ("HAZOP report.docx", DocType.HAZOP), ("random.pdf", None),
])
def test_suggest_doc_type(name, expected):
    assert suggest_doc_type(name) == expected


def test_suggest_number_revision():
    assert suggest_number_revision("GP-PID-001_RevC.dxf") == ("GP-PID-001", "C")
    assert suggest_number_revision("notes.pdf") == (None, None)
