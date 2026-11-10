from generate_sample_project import generate

from engcheck.core.models import DocType
from engcheck.ingest.extract import extract
from engcheck.ingest.parsers import parse_file


def _extract_all(tmp_path):
    return {d.doc_number: extract(parse_file(d.path), d.doc_type) for d in generate(tmp_path)}


def _value(ex, tag, param):
    return next(p.si_value for p in ex.params if p.tag == tag and p.param == param)


def test_sample_generates_six_parsable_docs(tmp_path):
    docs = generate(tmp_path)
    assert len(docs) == 6
    assert {d.doc_type for d in docs} == {DocType.PID, DocType.EQUIPMENT_LIST, DocType.LINE_LIST,
                                          DocType.DATASHEET, DocType.MATERIAL_SPEC}
    for d in docs:
        assert d.path.exists() and d.doc_number and d.revision
        assert extract(parse_file(d.path), d.doc_type).tags, d.path.name


def test_seeded_values_present(tmp_path):
    ex = _extract_all(tmp_path)
    assert _value(ex["GP-PID-001"], "V-101", "design_pressure") == 1600.0
    assert _value(ex["GP-EQL-001"], "V-101", "design_pressure") == 1600.0
    assert _value(ex["GP-DS-V101"], "V-101", "design_pressure") == 1400.0
    assert _value(ex["GP-EQL-001"], "P-101A", "power") == 45.0
    assert _value(ex["GP-DS-P101"], "P-101A", "power") == 55.0
    assert _value(ex["GP-EQL-001"], "V-102", "design_pressure") == 500.0
    assert _value(ex["GP-EQL-001"], "V-102", "operating_pressure") == 700.0
    assert "E-102" in {t.tag for t in ex["GP-PID-001"].tags}
    assert "E-102" not in {t.tag for t in ex["GP-EQL-001"].tags}
    assert '6"-AM-1004-A1A' in {t.tag for t in ex["GP-LL-001"].tags}
    assert '6"-AM-1004-A1A' not in {t.tag for t in ex["GP-PID-001"].tags}
    assert ("GP-PID-001", "A", 1) in ex["GP-DS-V101"].refs
    assert {t.tag for t in ex["GP-MS-001"].tags} == {"A1A", "B1A"}


def test_pump_b_material_blank_on_datasheet_page_two(tmp_path):
    ex = _extract_all(tmp_path)["GP-DS-P101"]
    b = [p for p in ex.params if p.tag == "P-101B"]
    assert b and all(p.page_no == 2 for p in b)
    assert "material" not in {p.param for p in b}
    assert "material" in {p.param for p in ex.params if p.tag == "P-101A"}


def test_equal_pressure_in_different_units(tmp_path):
    ex = _extract_all(tmp_path)
    a = _value(ex["GP-EQL-001"], "V-101", "operating_pressure")
    b = _value(ex["GP-DS-V101"], "V-101", "operating_pressure")
    assert a != b and abs(a - b) / a < 0.01


def test_no_unknown_units_in_sample(tmp_path):
    for ex in _extract_all(tmp_path).values():
        assert all(p.unit_known for p in ex.params)
