from engcheck.core.models import Confidence, Method, Severity
from engcheck.review.rules.r001 import R001
from engcheck.review.rules.r002 import R002
from engcheck.review.rules.r003 import R003
from engcheck.review.rules.r004 import R004
from engcheck.review.rules.r005 import R005
from engcheck.review.rules.r006 import R006
from engcheck.review.rules.r007 import R007

from .factories import DS, EQL, LL, MS, PID, PIPE_CLASS, make_doc, make_param, make_ref, make_tag


# ---- R001 ----
def test_r001_flags_mismatch_and_is_critical_for_pressure(db, project):
    a, b = make_doc(db, project, PID, "GP-PID-001"), make_doc(db, project, DS, "GP-DS-V101")
    make_param(db, project, a, "V-101", "design_pressure", "16 barg", 1600.0)
    make_param(db, project, b, "V-101", "design_pressure", "14 barg", 1400.0)
    (d,) = R001().check(db, project.id)
    assert d.rule_code == "R001" and d.param == "design_pressure" and d.tag_text == "V-101"
    assert d.severity == Severity.critical and d.confidence == Confidence.high
    assert sorted(e.value for e in d.evidence) == ["14 barg", "16 barg"]
    assert {e.document_id for e in d.evidence} == {a.id, b.id}


def test_r001_power_mismatch_is_major(db, project):
    a, b = make_doc(db, project, EQL), make_doc(db, project, DS)
    make_param(db, project, a, "P-101A", "power", "45", 45.0)
    make_param(db, project, b, "P-101A", "power", "55 kW", 55.0)
    assert R001().check(db, project.id)[0].severity == Severity.major


def test_r001_within_tolerance_ok(db, project):
    a, b = make_doc(db, project, EQL), make_doc(db, project, DS)
    make_param(db, project, a, "V-101", "operating_pressure", "12", 1200.0)
    make_param(db, project, b, "V-101", "operating_pressure", "174 psig", 1199.69)
    assert R001().check(db, project.id) == []


def test_r001_just_over_tolerance_flagged(db, project):
    a, b = make_doc(db, project, EQL), make_doc(db, project, DS)
    make_param(db, project, a, "V-101", "operating_pressure", "1000", 1000.0)
    make_param(db, project, b, "V-101", "operating_pressure", "1011", 1011.0)
    assert len(R001().check(db, project.id)) == 1


def test_r001_text_case_and_space_insensitive(db, project):
    a, b = make_doc(db, project, EQL), make_doc(db, project, DS)
    make_param(db, project, a, "P-101A", "material", "SS316")
    make_param(db, project, b, "P-101A", "material", "ss 316 ")
    assert R001().check(db, project.id) == []


def test_r001_text_mismatch_flagged(db, project):
    a, b = make_doc(db, project, EQL), make_doc(db, project, DS)
    make_param(db, project, a, "P-101A", "material", "SS316")
    make_param(db, project, b, "P-101A", "material", "CS")
    assert len(R001().check(db, project.id)) == 1


def test_r001_same_document_twice_not_compared(db, project):
    a = make_doc(db, project, EQL)
    make_param(db, project, a, "V-101", "design_pressure", "16", 1600.0)
    make_param(db, project, a, "V-101", "design_pressure", "10", 1000.0)
    assert R001().check(db, project.id) == []


def test_r001_regex_or_medium_evidence_lowers_confidence(db, project):
    a, b = make_doc(db, project, EQL), make_doc(db, project, DS)
    make_param(db, project, a, "V-101", "design_pressure", "16 bar", 1600.0, confidence=Confidence.medium)
    make_param(db, project, b, "V-101", "design_pressure", "14 barg", 1400.0)
    assert R001().check(db, project.id)[0].confidence == Confidence.medium


def test_r001_values_without_si_not_compared(db, project):
    a, b = make_doc(db, project, EQL), make_doc(db, project, DS)
    make_param(db, project, a, "V-101", "design_pressure", "16", None, number=16, unit_known=False)
    make_param(db, project, b, "V-101", "design_pressure", "14 barg", 1400.0)
    assert R001().check(db, project.id) == []


# ---- R002 ----
def test_r002_both_directions(db, project):
    pid, eql = make_doc(db, project, PID), make_doc(db, project, EQL)
    make_tag(db, project, pid, "E-101"); make_tag(db, project, eql, "E-101")
    make_tag(db, project, pid, "E-102")
    make_tag(db, project, eql, "V-900")
    got = {(d.tag_text, d.args["present_in"], d.args["missing_in"]) for d in R002().check(db, project.id)}
    assert got == {("E-102", "PID", "EQUIPMENT_LIST"), ("V-900", "EQUIPMENT_LIST", "PID")}


def test_r002_lines_against_line_list(db, project):
    pid, ll = make_doc(db, project, PID), make_doc(db, project, LL)
    make_tag(db, project, pid, '10"-HC-1001-A1A', method=Method.regex)
    make_tag(db, project, ll, '10"-HC-1001-A1A')
    make_tag(db, project, ll, '6"-AM-1004-A1A')
    (d,) = R002().check(db, project.id)
    assert d.tag_text == '6"-AM-1004-A1A' and d.severity == Severity.major
    assert d.confidence == Confidence.high and d.param is None


def test_r002_regex_evidence_is_medium(db, project):
    pid, ll = make_doc(db, project, PID), make_doc(db, project, LL)
    make_tag(db, project, pid, '4"-AM-1005-B2C', method=Method.regex)
    make_tag(db, project, ll, '6"-AM-1004-A1A')
    by_tag = {d.tag_text: d for d in R002().check(db, project.id)}
    assert by_tag['4"-AM-1005-B2C'].confidence == Confidence.medium


def test_r002_skipped_when_counterpart_doc_type_absent(db, project):
    pid = make_doc(db, project, PID)
    make_tag(db, project, pid, "E-102"); make_tag(db, project, pid, '6"-AM-1004-A1A')
    assert R002().check(db, project.id) == []


def test_r002_datasheet_one_way_only(db, project):
    eql, ds = make_doc(db, project, EQL), make_doc(db, project, DS)
    make_tag(db, project, eql, "V-101"); make_tag(db, project, eql, "E-101")
    make_tag(db, project, ds, "V-101"); make_tag(db, project, ds, "V-555")
    assert [d.tag_text for d in R002().check(db, project.id)] == ["V-555"]


def test_r002_instruments_ignored(db, project):
    pid, eql = make_doc(db, project, PID), make_doc(db, project, EQL)
    make_tag(db, project, pid, "PT-1001"); make_tag(db, project, eql, "V-101"); make_tag(db, project, pid, "V-101")
    assert R002().check(db, project.id) == []


# ---- R003 ----
def test_r003_missing_material_on_datasheet(db, project):
    ds = make_doc(db, project, DS)
    make_param(db, project, ds, "P-101B", "power", "45 kW", 45.0, page=2)
    (d,) = R003().check(db, project.id)
    assert (d.tag_text, d.param, d.severity, d.confidence) == ("P-101B", "material", Severity.minor, Confidence.high)
    assert d.evidence[0].document_id == ds.id and d.evidence[0].page_no == 2


def test_r003_pump_does_not_need_design_pressure(db, project):
    ds = make_doc(db, project, DS)
    make_param(db, project, ds, "P-101A", "material", "SS316")
    assert R003().check(db, project.id) == []


def test_r003_vessel_needs_design_conditions_as_major(db, project):
    ds = make_doc(db, project, DS)
    make_param(db, project, ds, "V-101", "material", "CS")
    got = {(d.param, d.severity) for d in R003().check(db, project.id)}
    assert got == {("design_pressure", Severity.major), ("design_temperature", Severity.major)}


def test_r003_line_list_required_fields(db, project):
    ll = make_doc(db, project, LL)
    make_param(db, project, ll, '6"-AM-1004-A1A', "size", '6"', 152.4)
    assert {d.param for d in R003().check(db, project.id)} == {"fluid", "pipe_class"}


def test_r003_tag_only_mentioned_is_not_a_row(db, project):
    ds = make_doc(db, project, DS)
    make_tag(db, project, ds, "V-101", method=Method.regex)
    assert R003().check(db, project.id) == []


def test_r003_equipment_list_has_no_required_fields(db, project):
    eql = make_doc(db, project, EQL)
    make_param(db, project, eql, "V-101", "power", "1", 1.0)
    assert R003().check(db, project.id) == []


# ---- R004 ----
def test_r004_design_below_operating(db, project):
    eql = make_doc(db, project, EQL)
    make_param(db, project, eql, "V-102", "design_pressure", "5", 500.0)
    make_param(db, project, eql, "V-102", "operating_pressure", "7", 700.0)
    (d,) = R004().check(db, project.id)
    assert (d.tag_text, d.param, d.severity, d.confidence) == ("V-102", "design_pressure", Severity.critical, Confidence.high)
    assert sorted(e.value for e in d.evidence) == ["5", "7"]


def test_r004_equal_is_ok(db, project):
    eql = make_doc(db, project, EQL)
    make_param(db, project, eql, "V-102", "design_temperature", "120", 120.0)
    make_param(db, project, eql, "V-102", "operating_temperature", "120", 120.0)
    assert R004().check(db, project.id) == []


def test_r004_temperature_across_documents(db, project):
    eql, ds = make_doc(db, project, EQL), make_doc(db, project, DS)
    make_param(db, project, eql, "E-101", "design_temperature", "100", 100.0)
    make_param(db, project, ds, "E-101", "operating_temperature", "110", 110.0)
    (d,) = R004().check(db, project.id)
    assert d.param == "design_temperature" and {e.document_id for e in d.evidence} == {eql.id, ds.id}


# ---- R005 ----
def test_r005_class_missing_from_spec(db, project):
    ll, ms = make_doc(db, project, LL), make_doc(db, project, MS)
    make_tag(db, project, ms, "A1A", PIPE_CLASS)
    make_param(db, project, ll, '8"-AM-1002-A1A', "pipe_class", "A1A")
    make_param(db, project, ll, '4"-AM-1005-B2C', "pipe_class", "b2c")
    make_param(db, project, ll, '2"-AM-1006-B2C', "pipe_class", "B2C")
    (d,) = R005().check(db, project.id)
    assert (d.tag_text, d.param, d.tag_id, d.severity) == ("B2C", "pipe_class", None, Severity.major)
    assert len(d.evidence) == 2


def test_r005_skipped_without_material_spec(db, project):
    ll = make_doc(db, project, LL)
    make_param(db, project, ll, '4"-AM-1005-B2C', "pipe_class", "B2C")
    assert R005().check(db, project.id) == []


# ---- R006 ----
def test_r006_stale_revision(db, project):
    make_doc(db, project, PID, "GP-PID-001", "C")
    ds = make_doc(db, project, DS, "GP-DS-V101", "A")
    make_ref(db, ds, "GP-PID-001", "A")
    (d,) = R006().check(db, project.id)
    assert (d.tag_id, d.param, d.severity, d.confidence) == (None, None, Severity.minor, Confidence.medium)
    assert d.args == {"doc": "GP-DS-V101", "ref_doc": "GP-PID-001", "ref_rev": "A", "current_rev": "C"}
    assert d.evidence[0].document_id == ds.id


def test_r006_current_revision_ok_and_self_reference_ignored(db, project):
    pid = make_doc(db, project, PID, "GP-PID-001", "C")
    ds = make_doc(db, project, DS, "GP-DS-V101", "A")
    make_ref(db, ds, "GP-PID-001", "c")
    make_ref(db, pid, "GP-PID-001", "B")
    assert R006().check(db, project.id) == []


def test_r006_unknown_doc_number_ignored(db, project):
    ds = make_doc(db, project, DS, "GP-DS-V101", "A")
    make_ref(db, ds, "ZZ-PID-999", "A")
    assert R006().check(db, project.id) == []


# ---- R007 ----
def test_r007_unknown_unit(db, project):
    eql = make_doc(db, project, EQL)
    make_param(db, project, eql, "V-101", "design_pressure", "16 foo", None, number=16, unit_known=False)
    make_param(db, project, eql, "V-101", "material", "CS")
    (d,) = R007().check(db, project.id)
    assert (d.tag_text, d.param, d.severity, d.confidence) == ("V-101", "design_pressure", Severity.minor, Confidence.high)


def test_rules_ignore_other_projects(db, project):
    from engcheck.core.models import Project, Stage
    other = Project(name="o", industry="gtl", stage=Stage.FEED)
    db.add(other); db.flush()
    a, b = make_doc(db, other, PID), make_doc(db, other, DS)
    make_param(db, other, a, "V-101", "design_pressure", "16", 1600.0)
    make_param(db, other, b, "V-101", "design_pressure", "14", 1400.0)
    assert R001().check(db, project.id) == []
