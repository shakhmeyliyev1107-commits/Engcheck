import pytest

from engcheck.ingest.units import PARAM_KIND, parse_quantity


@pytest.mark.parametrize("text,param,hint,si", [
    ("16 barg", "design_pressure", None, 1600.0),
    ("16barg", "design_pressure", None, 1600.0),
    ("174 psig", "operating_pressure", None, 1199.69),
    ("10,5", "design_pressure", "barg", 1050.0),
    ("2 bara", "design_pressure", None, 98.675),
    ("1.6 MPa", "design_pressure", None, 1600.0),
    ("1600 кПа", "design_pressure", None, 1600.0),
    ("120 °C", "design_temperature", None, 120.0),
    ("212 °F", "design_temperature", None, 100.0),
    ("373.15 K", "design_temperature", None, 100.0),
    ("-29 °C", "design_temperature", None, -29.0),
    ('6"', "size", None, 152.4),
    ("6 in", "size", None, 152.4),
    ("DN150", "size", None, 150.0),
    ("55 кВт", "power", None, 55.0),
    ("75 hp", "power", None, 55.927),
    ("100 gpm", "flow_rate", None, 22.712),
    ("120 m3/h", "flow_rate", None, 120.0),
    ("1 200 kPa", "design_pressure", None, 1200.0),
])
def test_si_conversion(text, param, hint, si):
    q = parse_quantity(text, param, hint)
    assert q.unit_known
    assert q.si_value == pytest.approx(si, rel=1e-3)


def test_si_units_per_kind():
    assert parse_quantity("16 barg", "design_pressure").si_unit == "kPa(g)"
    assert parse_quantity("120 C", "design_temperature").si_unit == "°C"
    assert parse_quantity("10 m3/h", "flow_rate").si_unit == "m³/h"
    assert parse_quantity("DN50", "size").si_unit == "mm"
    assert parse_quantity("5 kW", "power").si_unit == "kW"


def test_gauge_unit_is_not_assumed():
    assert parse_quantity("16 barg", "design_pressure").assumed is False


def test_bare_bar_is_assumed_gauge():
    q = parse_quantity("16 bar", "design_pressure")
    assert q.assumed and q.si_value == 1600.0


def test_cell_unit_wins_over_hint():
    assert parse_quantity("232 psig", "design_pressure", "barg").si_value == pytest.approx(1599.58, rel=1e-3)


def test_unknown_unit():
    q = parse_quantity("16 foo", "design_pressure")
    assert q.number == 16 and q.si_value is None and q.unit_known is False


def test_number_without_any_unit_is_unknown():
    q = parse_quantity("16", "design_pressure")
    assert q.number == 16 and q.si_value is None and q.unit_known is False


def test_text_param_passthrough():
    q = parse_quantity("  CS A516 Gr.70 ", "material")
    assert q.raw == "CS A516 Gr.70" and q.unit_known and q.number is None and q.si_value is None


def test_empty_is_none_number():
    q = parse_quantity("", "power")
    assert q.number is None and q.si_value is None


def test_range_is_not_misparsed_as_number():
    q = parse_quantity("-29/150 °C", "design_temperature")
    assert q.number is None and q.unit_known is True


def test_non_numeric_placeholder_in_numeric_param():
    q = parse_quantity("N/A", "design_pressure")
    assert q.number is None and q.unit_known is True


def test_unknown_param_treated_as_text():
    assert parse_quantity("abc", "something_else").number is None


def test_param_kinds():
    assert PARAM_KIND["design_pressure"] == "pressure"
    assert PARAM_KIND["material"] == "text"
    assert PARAM_KIND["pipe_class"] == "text"
