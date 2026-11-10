import pytest
from sqlalchemy.exc import IntegrityError

from engcheck.core.models import (Document, DocType, Discipline, FindingStatus, ParseStatus,
                                  Project, Role, Severity, Stage, Tag, TagClass, Confidence)


def _project(db):
    p = Project(name="GP", industry="gas_processing", stage=Stage.DD)
    db.add(p)
    db.flush()
    return p


def test_tag_unique_per_project(db):
    p = _project(db)
    db.add_all([Tag(project_id=p.id, tag="V-101", tag_class=TagClass.equipment),
                Tag(project_id=p.id, tag="V-101", tag_class=TagClass.equipment)])
    with pytest.raises(IntegrityError):
        db.flush()


def test_document_sha_unique_per_project(db):
    p = _project(db)
    kw = dict(project_id=p.id, doc_type=DocType.PID, discipline=Discipline.process, sha256="a" * 64)
    db.add_all([Document(filename="a.dxf", **kw), Document(filename="b.dxf", **kw)])
    with pytest.raises(IntegrityError):
        db.flush()


def test_same_tag_allowed_in_other_project(db):
    p1, p2 = _project(db), _project(db)
    db.add_all([Tag(project_id=p1.id, tag="V-101", tag_class=TagClass.equipment),
                Tag(project_id=p2.id, tag="V-101", tag_class=TagClass.equipment)])
    db.flush()


def test_enum_values_match_spec():
    assert [s.value for s in Severity] == ["critical", "major", "minor", "info"]
    assert [s.value for s in FindingStatus] == ["new", "reviewed", "confirmed", "rejected", "fixed"]
    assert [s.value for s in Role] == ["admin", "lead", "engineer", "viewer"]
    assert [s.value for s in Stage] == ["FEED", "DD", "AS_BUILT"]
    assert [s.value for s in Confidence] == ["high", "medium", "low"]
    assert [s.value for s in ParseStatus] == ["pending", "parsed", "needs_ocr", "unsupported", "error"]
    assert [s.value for s in DocType] == ["PFD", "PID", "DATASHEET", "EQUIPMENT_LIST", "LINE_LIST",
                                          "MATERIAL_SPEC", "CALCULATION", "HAZOP", "HAZID", "OTHER"]
    assert [s.value for s in Discipline] == ["process", "mechanical", "piping", "instrumentation",
                                             "electrical", "civil", "hse", "technical"]
    assert [s.value for s in TagClass] == ["equipment", "line", "instrument", "pipe_class"]


def test_document_defaults_to_pending(db):
    p = _project(db)
    d = Document(project_id=p.id, filename="a.pdf", doc_type=DocType.PFD,
                 discipline=Discipline.process, sha256="b" * 64)
    db.add(d)
    db.flush()
    assert d.parse_status == ParseStatus.pending
