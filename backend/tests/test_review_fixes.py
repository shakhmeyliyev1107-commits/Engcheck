"""Yakuniy ko'rikda topilgan holatlar: haqiqiy hujjatlarga xos kiritishlar."""
import time

import openpyxl
import pytest

from engcheck.core.models import (Confidence, Discipline, DocType, Finding, FindingStatus, Method,
                                  ParseStatus, Session, Severity, Tag, TagClass)
from engcheck.ingest.extract import extract
from engcheck.ingest.headers import match_header
from engcheck.ingest.model import Cell, Page, ParsedDocument, Table, TextItem
from engcheck.ingest.parsers import ParseError, parse_file
from engcheck.ingest.service import ingest_file
from engcheck.ingest.tagging import find_tags, normalize_tags
from engcheck.ingest.units import parse_quantity
from engcheck.review.engine import run_review
from engcheck.review.rules.r001 import R001
from engcheck.review.rules.r002 import R002
from engcheck.review.rules.r004 import R004
from engcheck.review.rules.r006 import R006
from engcheck.review.rules.r007 import R007

from .review.factories import DS, EQL, LL, PID, make_doc, make_param, make_ref, make_tag


def table(rows):
    return Table([[Cell(v, f"S!{chr(65 + c)}{r + 1}") for c, v in enumerate(row)] for r, row in enumerate(rows)])


def xlsx(path, rows):
    wb = openpyxl.Workbook()
    for row in rows:
        wb.active.append(row)
    wb.save(path)
    return path


def findings(db, project):
    run = run_review(db, project.id, None)
    return [(f.rule.code, f.tag_text, f.param) for f in db.query(Finding).filter_by(run_id=run.id)]


# ---- 1, 3, 4: teg yozilishi va sinfi ----
@pytest.mark.parametrize("raw,expected", [
    ("P-101A/B", ["P-101A", "P-101B"]), ("V-101 (NEW)", ["V-101"]), ("P–101A", ["P-101A"]),
    ("Р-101А", ["P-101A"]),                      # kirill harflari
    ('3/4"-HC-1001-A1A', ['3/4"-HC-1001-A1A']), ('1 1/2"-AM-1002-A1A', ['1-1/2"-AM-1002-A1A']),
    ('10"-HC-1003-A1A-H', ['10"-HC-1003-A1A-H']), ("10-P-101A", ["10-P-101A"]),
    ("P-101A, P-101B", ["P-101A", "P-101B"]), ("Total", []), ("", []),
])
def test_normalize_tags_real_world_spellings(raw, expected):
    assert normalize_tags(raw) == expected


def test_find_tags_fractional_line_keeps_its_size():
    assert [t for t, _ in find_tags('Line 3/4"-HC-1001-A1A and 1 1/2"-AM-1002-A1A')] == [
        '3/4"-HC-1001-A1A', '1-1/2"-AM-1002-A1A']


def test_find_tags_expands_a_b_suffix():
    assert [t for t, _ in find_tags("Pumps P-101A/B")] == ["P-101A", "P-101B"]


@pytest.mark.parametrize("tag", ["XV-1001", "HV-101", "PDT-101", "SDV-101", "ZSO-1001"])
def test_valve_and_instrument_tags_are_instruments(tag):
    assert find_tags(tag) == [(tag, TagClass.instrument)]


def test_tag_variants_do_not_create_phantom_tag_end_to_end(db, settings, project, tmp_path):
    eql = xlsx(tmp_path / "GP-EQL-001_RevA.xlsx", [["Tag No.", "Material"], ["p-101 a", "CS"], ["P101B", "CS"]])
    pid = xlsx(tmp_path / "GP-PID-001_RevA.xlsx", [["Tag No.", "Material"], ["P-101A", "CS"], ["P-101B", "CS"]])
    ingest_file(db, settings, project.id, None, eql, eql.name, DocType.EQUIPMENT_LIST, Discipline.mechanical)
    ingest_file(db, settings, project.id, None, pid, pid.name, DocType.PID, Discipline.process)
    assert sorted(t.tag for t in db.query(Tag)) == ["P-101A", "P-101B"]
    assert findings(db, project) == []


def test_equipment_list_tag_column_is_equipment_whatever_it_looks_like(db, settings, project, tmp_path):
    eql = xlsx(tmp_path / "eql.xlsx", [["Tag No.", "Material"], ["AC-101", "CS"], ["FL-101", "CS"], ["PC-101", "CS"]])
    pid = xlsx(tmp_path / "pid.xlsx", [["Tag No.", "Material"], ["AC-101", "CS"]])
    ingest_file(db, settings, project.id, None, pid, "pid.xlsx", DocType.PID, Discipline.process)
    ingest_file(db, settings, project.id, None, eql, "eql.xlsx", DocType.EQUIPMENT_LIST, Discipline.mechanical)
    assert {t.tag: t.tag_class for t in db.query(Tag)} == {"AC-101": "equipment", "FL-101": "equipment", "PC-101": "equipment"}
    assert sorted(findings(db, project)) == [("R002", "FL-101", None), ("R002", "PC-101", None)]


def test_a_b_row_feeds_both_tags_and_unrecognised_rows_are_reported():
    t = table([["Tag No.", "Motor Power, kW"], ["P-101A/B", "45"], ["see note 3", "1"], ["V_101?", "2"]])
    ex = extract(ParsedDocument([Page(1, "", [t])]), DocType.EQUIPMENT_LIST)
    assert [(p.tag, p.si_value) for p in ex.params] == [("P-101A", 45.0), ("P-101B", 45.0)]
    assert ex.skipped_tags == ["see note 3", "V_101?"]


def test_skipped_tags_are_saved_on_document(db, settings, project, tmp_path):
    p = xlsx(tmp_path / "eql.xlsx", [["Tag No.", "Material"], ["V-101", "CS"], ["???", "CS"]])
    doc = ingest_file(db, settings, project.id, None, p, "eql.xlsx", DocType.EQUIPMENT_LIST, Discipline.mechanical)
    assert doc.skipped_tags == ["???"]


# ---- 2: haqiqiy P&ID matni R002 ni to'ldirib yubormaydi ----
def test_r002_ignores_free_text_tags_with_unknown_prefix(db, project):
    pid, eql = make_doc(db, project, PID), make_doc(db, project, EQL)
    make_tag(db, project, eql, "P-101A"); make_tag(db, project, pid, "P-101A", method=Method.regex)
    for noise in ("API-610", "ISO-9001", "DN-100", "A-106", "REV-001"):
        make_tag(db, project, pid, noise, TagClass.equipment, method=Method.regex)
    make_tag(db, project, pid, "P-102", TagClass.equipment, method=Method.regex)   # prefiks ro'yxatda bor
    assert [d.tag_text for d in R002().check(db, project.id)] == ["P-102"]


def test_r002_block_attribute_equipment_always_checked(db, project):
    pid, eql = make_doc(db, project, PID), make_doc(db, project, EQL)
    make_tag(db, project, eql, "V-101"); make_tag(db, project, pid, "V-101")
    make_tag(db, project, pid, "E-102", TagClass.equipment, method=Method.cell)    # "E" ro'yxatda yo'q
    assert [d.tag_text for d in R002().check(db, project.id)] == ["E-102"]


# ---- 5: birliklar qatori va DN ustuni ----
def test_units_row_under_header_is_used_as_hint():
    t = table([["Line No.", "Size", "Design Pressure", "Design Temperature"], ["", "in", "barg", "°C"],
               ['6"-AM-1004-A1A', "6", "16", "150"]])
    ex = extract(ParsedDocument([Page(1, "", [t])]), DocType.LINE_LIST)
    got = {p.param: (p.si_value, p.unit_known) for p in ex.params}
    assert got == {"size": (152.4, True), "design_pressure": (1600.0, True), "design_temperature": (150.0, True)}
    assert ex.skipped_tags == []


def test_dn_and_nps_headers_imply_unit():
    assert match_header("DN") == ("size", "DN") and match_header("NPS") == ("size", "NPS")
    assert parse_quantity("150", "size", "DN").si_value == 150.0
    assert parse_quantity("6", "size", "NPS").si_value == 152.4


# ---- 6: uzoqdagi adashgan katak ----
def test_stray_far_cell_does_not_hang_xlsx(tmp_path):
    p = tmp_path / "a.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Tag No.", "Material"]); ws.append(["V-101", "CS"])
    ws.cell(3000, 2000).value = " "
    wb.save(p)
    start = time.monotonic()
    rows = parse_file(p).pages[0].tables[0].rows
    assert time.monotonic() - start < 5
    assert len(rows) == 2 and len(rows[0]) == 2 and rows[1][0].location == "Sheet!A2"


def test_oversized_sheet_is_rejected_not_hung(tmp_path):
    p = tmp_path / "a.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.cell(1, 1).value = "x"; ws.cell(4000, 4000).value = "y"
    wb.save(p)
    with pytest.raises(ParseError) as e:
        parse_file(p)
    assert e.value.code == "corrupt" and "katta" in str(e.value)


# ---- 7: reviziyalar ----
def test_superseded_revision_is_not_compared(db, project):
    eql = make_doc(db, project, EQL, "GP-EQL-001", "B")
    old, new = make_doc(db, project, DS, "GP-DS-001", "A"), make_doc(db, project, DS, "GP-DS-001", "B")
    make_param(db, project, eql, "V-101", "design_pressure", "16", 1600.0)
    make_param(db, project, old, "V-101", "design_pressure", "14 barg", 1400.0)
    make_param(db, project, new, "V-101", "design_pressure", "16 barg", 1600.0)
    assert R001().check(db, project.id) == []


def test_numeric_revision_outranks_letter_and_upload_order_is_irrelevant(db, project):
    make_doc(db, project, PID, "GP-PID-001", "0")
    make_doc(db, project, PID, "GP-PID-001", "C")          # eski reviziya keyinroq yuklangan
    ds = make_doc(db, project, DS, "GP-DS-V101", "A")
    make_ref(db, ds, "GP-PID-001", "0")
    assert R006().check(db, project.id) == []
    make_ref(db, ds, "GP-PID-001", "C")
    (d,) = R006().check(db, project.id)
    assert d.description_key == "r006_stale_revision" and d.args["current_rev"] == "0"


def test_reference_to_newer_revision_than_loaded_is_worded_differently(db, project):
    make_doc(db, project, PID, "GP-PID-001", "C")
    ds = make_doc(db, project, DS, "GP-DS-V101", "A")
    make_ref(db, ds, "GP-PID-001", "D")
    (d,) = R006().check(db, project.id)
    assert d.description_key == "r006_newer_revision" and d.args["current_rev"] == "C"


def test_reference_detection_is_case_insensitive():
    ex = extract(ParsedDocument([Page(1, "SEE GP-PID-001 REV A and gp-eql-001 rev.b", [], [])]), DocType.DATASHEET)
    assert ex.refs == [("GP-PID-001", "A", 1), ("GP-EQL-001", "B", 1)]


# ---- 8: manfiy harorat ----
def test_r004_cryogenic_design_temperature_is_a_minimum(db, project):
    eql = make_doc(db, project, EQL)
    make_param(db, project, eql, "V-201", "design_temperature", "-196 °C", -196.0)
    make_param(db, project, eql, "V-201", "operating_temperature", "-160 °C", -160.0)
    assert R004().check(db, project.id) == []


def test_r004_operating_colder_than_minimum_design_temperature(db, project):
    eql = make_doc(db, project, EQL)
    make_param(db, project, eql, "V-201", "design_temperature", "-29 °C", -29.0)
    make_param(db, project, eql, "V-201", "operating_temperature", "-46 °C", -46.0)
    (d,) = R004().check(db, project.id)
    assert d.description_key == "r004_min_design_above_operating" and d.severity == Severity.critical
    assert d.confidence == Confidence.medium


# ---- 9, 10: qiymat yozilishi ----
@pytest.mark.parametrize("text,param,hint,si", [
    ("−46", "design_temperature", "°C", -46.0), ("–29 °C", "design_temperature", None, -29.0),
    ("≤ 16", "design_pressure", "barg", 1600.0), ("16 barg (Note 1)", "design_pressure", None, 1600.0),
    ("3.5 / FV", "design_pressure", "barg", 350.0), ("1,200.5 kPa", "design_pressure", None, 1200.5),
    ("1.200,5 kPa", "design_pressure", None, 1200.5), ("1,200,000 W", "power", None, 1200.0),
    ("0,125 MPa", "design_pressure", None, 125.0),
])
def test_value_spellings(text, param, hint, si):
    q = parse_quantity(text, param, hint)
    assert q.unit_known and q.si_value == pytest.approx(si)


def test_ambiguous_comma_group_is_not_guessed():
    q = parse_quantity("1,200 kPa", "design_pressure")      # 1200 ham, 1.2 ham bo'lishi mumkin
    assert q.number is None and q.si_value is None


def test_unparsed_numeric_value_is_reported_not_silently_dropped(db, project):
    eql = make_doc(db, project, EQL)
    make_param(db, project, eql, "V-101", "design_temperature", "-29 / 150 °C", None, number=None)
    make_param(db, project, eql, "V-101", "design_pressure", "N/A", None, number=None)
    make_param(db, project, eql, "V-101", "material", "CS")
    (d,) = R007().check(db, project.id)
    assert (d.description_key, d.param, d.severity) == ("r007_unparsed_value", "design_temperature", Severity.info)


# ---- 12, 14, 15 ----
def test_carried_fixed_reopens_as_confirmed(db, project):
    a, b = make_doc(db, project, PID, "GP-PID-001"), make_doc(db, project, EQL, "GP-EQL-001")
    make_param(db, project, a, "V-101", "design_pressure", "16 barg", 1600.0)
    make_param(db, project, b, "V-101", "design_pressure", "14 barg", 1400.0)
    run = run_review(db, project.id, None)
    db.query(Finding).filter_by(run_id=run.id).one().status = FindingStatus.fixed
    db.flush()
    run2 = run_review(db, project.id, None)
    assert db.query(Finding).filter_by(run_id=run2.id).one().status == FindingStatus.confirmed


def test_password_reset_revokes_sessions(db):
    from engcheck.core.auth import create_user, login, set_password, user_for_token
    u = create_user(db, "aziz", "S3cret-pass", "engineer")
    tok = login(db, "aziz", "S3cret-pass")
    set_password(db, u, "N3w-secret-pass")
    assert user_for_token(db, tok) is None and db.query(Session).count() == 0
    assert login(db, "aziz", "N3w-secret-pass")
