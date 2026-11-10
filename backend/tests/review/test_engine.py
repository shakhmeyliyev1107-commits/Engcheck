import pytest

from engcheck.core.models import (AuditLog, Finding, FindingAction, FindingStatus, Rule, Standard,
                                  TagParam)
from engcheck.review import engine
from engcheck.review.engine import run_review, seed_rules, source_text
from engcheck.review.messages import render

from .factories import DS, EQL, PID, make_doc, make_param


@pytest.fixture
def mismatch(db, project):
    a, b = make_doc(db, project, PID, "GP-PID-001"), make_doc(db, project, EQL, "GP-EQL-001")
    make_param(db, project, a, "V-101", "design_pressure", "16 barg", 1600.0)
    return make_param(db, project, b, "V-101", "design_pressure", "14 barg", 1400.0)


def _findings(db, run):
    return db.query(Finding).filter_by(run_id=run.id).all()


def test_seed_rules_is_idempotent(db):
    seed_rules(db)
    seed_rules(db)
    rules = db.query(Rule).order_by(Rule.code).all()
    assert [r.code for r in rules] == ["R001", "R002", "R003", "R004", "R005", "R006", "R007"]
    assert all(r.title_uz and r.title_en and r.title_ru and r.enabled for r in rules)


def test_run_persists_findings_with_evidence_and_text(db, project, mismatch):
    run = run_review(db, project.id, None)
    (f,) = _findings(db, run)
    assert f.rule.code == "R001" and f.tag_text == "V-101" and f.param == "design_pressure"
    assert f.status == FindingStatus.new and f.source_type == "rule" and run.ai_mode == "none"
    assert "V-101" in f.description and "16 barg" in f.rationale and f.recommendation
    assert len(f.evidence) == 2 and len(f.fingerprint) == 64
    assert run.errors == []


def test_run_is_audited(db, project, mismatch):
    from engcheck.core.auth import create_user
    from engcheck.core.models import Role
    user = create_user(db, "aziz", "S3cret-pass", Role.engineer)
    run = run_review(db, project.id, user.id)
    row = db.query(AuditLog).filter_by(action="review.run").one()
    assert row.object_id == run.id and row.user_id == user.id and run.started_by == user.id and row.details["findings"] == 1


def test_disabled_rule_not_run(db, project, mismatch):
    seed_rules(db)
    db.query(Rule).filter_by(code="R001").one().enabled = False
    db.flush()
    assert _findings(db, run_review(db, project.id, None)) == []


def test_failing_rule_recorded_and_others_continue(db, project, mismatch, monkeypatch):
    def boom(self, db, project_id):
        raise RuntimeError("kutilmagan")
    monkeypatch.setattr(type(engine.ALL_RULES[1]), "check", boom)
    run = run_review(db, project.id, None)
    assert run.errors == [{"rule": "R002", "error": "RuntimeError: kutilmagan"}]
    assert len(_findings(db, run)) == 1


def test_rerun_carries_decision_by_fingerprint(db, project, mismatch):
    (f1,) = _findings(db, run_review(db, project.id, None))
    f1.status = FindingStatus.rejected
    db.add(FindingAction(finding_id=f1.id, user_id=None, action="reject", comment="datasheet eskirgan"))
    db.flush()
    (f2,) = _findings(db, run_review(db, project.id, None))
    assert f2.id != f1.id and f2.status == FindingStatus.rejected
    assert [(a.action, a.comment, a.user_id) for a in f2.actions] == [("carried_over", "datasheet eskirgan", None)]
    (f3,) = _findings(db, run_review(db, project.id, None))
    assert f3.status == FindingStatus.rejected


def test_reviewed_status_is_not_carried(db, project, mismatch):
    (f1,) = _findings(db, run_review(db, project.id, None))
    f1.status = FindingStatus.reviewed
    db.flush()
    (f2,) = _findings(db, run_review(db, project.id, None))
    assert f2.status == FindingStatus.new


def test_changed_value_gets_new_finding(db, project, mismatch):
    (f1,) = _findings(db, run_review(db, project.id, None))
    f1.status = FindingStatus.confirmed
    mismatch.raw_value, mismatch.si_value = "12 barg", 1200.0
    db.flush()
    (f2,) = _findings(db, run_review(db, project.id, None))
    assert f2.fingerprint != f1.fingerprint and f2.status == FindingStatus.new


def test_resolved_issue_disappears(db, project, mismatch):
    run_review(db, project.id, None)
    mismatch.raw_value, mismatch.si_value = "16 barg", 1600.0
    db.flush()
    assert _findings(db, run_review(db, project.id, None)) == []


@pytest.mark.parametrize("key,args", [
    ("r001_mismatch", {"tag": "V-101", "param": "design_pressure", "values": "A: 16 barg; B: 14 barg"}),
    ("r002_missing", {"tag": "E-102", "present_in": "PID", "missing_in": "EQUIPMENT_LIST", "docs": "GP-PID-001"}),
    ("r003_missing_param", {"tag": "P-101B", "param": "material", "doc": "GP-DS-P101"}),
    ("r004_design_below_operating", {"tag": "V-102", "param": "design_pressure",
                                     "operating_param": "operating_pressure", "design": "X: 5", "operating": "X: 7"}),
    ("r005_class_undefined", {"pipe_class": "B2C", "lines": "L1", "spec": "GP-MS-001"}),
    ("r006_stale_revision", {"doc": "GP-DS-V101", "ref_doc": "GP-PID-001", "ref_rev": "A", "current_rev": "C"}),
    ("r007_unknown_unit", {"tag": "V-101", "param": "design_pressure", "value": "16 foo", "doc": "X"}),
])
def test_render_three_locales(key, args):
    uz, en, ru = (render(key, args, loc) for loc in ("uz", "en", "ru"))
    assert len({uz, en, ru}) == 3
    subject = args.get("tag") or args.get("pipe_class") or args["doc"]
    for parts in (uz, en, ru):
        assert len(parts) == 3 and all(parts) and subject in parts[0]
        assert "{" not in "".join(parts)


def test_render_localizes_parameter_names():
    args = {"tag": "V-101", "param": "design_pressure", "values": "x"}
    assert "loyiha bosimi" in render("r001_mismatch", args, "uz")[0]
    assert "design pressure" in render("r001_mismatch", args, "en")[0]
    assert "расчётное давление" in render("r001_mismatch", args, "ru")[0]


def test_render_unknown_locale_falls_back_to_uz():
    args = {"tag": "V-101", "param": "material", "doc": "X"}
    assert render("r003_missing_param", args, "de") == render("r003_missing_param", args, "uz")


def test_source_text_is_internal_inconsistency_without_standard(db):
    seed_rules(db)
    rule = db.query(Rule).filter_by(code="R001").one()
    assert source_text(rule, "uz") == "Loyiha hujjatlari o‘rtasidagi ichki nomuvofiqlik"
    assert source_text(rule, "en") == "Internal inconsistency between project documents"


def test_source_text_cites_only_active_standard(db):
    seed_rules(db)
    rule = db.query(Rule).filter_by(code="R004").one()
    std = Standard(code="ASME BPVC VIII-1", edition="2023", status="superseded")
    db.add(std); db.flush()
    rule.standard_id = std.id
    db.flush(); db.refresh(rule)
    assert "ASME" not in source_text(rule, "en")
    std.status = "active"
    db.flush()
    assert source_text(rule, "en") == "ASME BPVC VIII-1 (2023)"
