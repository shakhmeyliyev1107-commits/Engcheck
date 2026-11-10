"""Namunaviy gaz tozalash loyihasida to'liq oqim: yuklash -> ajratish -> tekshiruv."""
import pytest

from engcheck.core.models import Confidence, Finding, FindingEvidence, Severity
from engcheck.review.engine import run_review

EXPECTED = {
    ("R001", "V-101", "design_pressure"), ("R001", "P-101A", "power"),
    ("R002", "E-102", None), ("R002", '6"-AM-1004-A1A', None),
    ("R003", "P-101B", "material"), ("R004", "V-102", "design_pressure"),
    ("R005", "B2C", "pipe_class"), ("R006", None, None),
}


@pytest.fixture
def findings(db, project, ingest_sample):
    run = run_review(db, project.id, None)
    assert run.errors == []
    return db.query(Finding).filter_by(run_id=run.id).all()


def test_sample_project_yields_exactly_seeded_findings(findings):
    got = [(f.rule.code, f.tag_text, f.param) for f in findings]
    assert sorted(got, key=str) == sorted(EXPECTED, key=str)


def test_psi_vs_barg_equal_value_not_flagged(findings):
    assert ("R001", "V-101", "operating_pressure") not in {(f.rule.code, f.tag_text, f.param) for f in findings}


def test_severities(findings):
    sev = {(f.rule.code, f.tag_text): f.severity for f in findings}
    assert sev[("R001", "V-101")] == Severity.critical
    assert sev[("R004", "V-102")] == Severity.critical
    assert sev[("R001", "P-101A")] == Severity.major
    assert sev[("R003", "P-101B")] == Severity.minor
    assert sev[("R006", None)] == Severity.minor
    assert sum(1 for f in findings if f.severity == Severity.critical) == 2


def test_v101_mismatch_cites_all_three_documents(findings, ingest_sample):
    f = next(f for f in findings if f.rule.code == "R001" and f.tag_text == "V-101")
    assert {e.document_id for e in f.evidence} == {ingest_sample[n].id for n in
                                                   ("GP-PID-001", "GP-EQL-001", "GP-DS-V101")}
    assert sorted(e.value for e in f.evidence) == ["14 barg", "16", "16 barg"]
    assert f.confidence == Confidence.high


def test_missing_material_points_to_page_two(findings, ingest_sample):
    f = next(f for f in findings if f.rule.code == "R003")
    assert [(e.document_id, e.page_no) for e in f.evidence] == [(ingest_sample["GP-DS-P101"].id, 2)]


def test_every_finding_points_to_document_and_page(db, findings):
    for f in findings:
        assert f.evidence, f.description
        for e in f.evidence:
            assert e.document_id and e.page_no >= 1 and e.location
        assert f.description and f.rationale and f.recommendation and f.source_type == "rule"
    assert db.query(FindingEvidence).count() >= len(findings)
