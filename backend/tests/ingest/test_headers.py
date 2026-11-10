import pytest

from engcheck.ingest.headers import match_header


@pytest.mark.parametrize("h,exp", [
    ("Design Pressure, barg", ("design_pressure", "barg")),
    ("Loyiha bosimi (MPa)", ("design_pressure", "MPa")),
    ("Расчётное давление", ("design_pressure", None)),
    ("расчетное давление, кПа", ("design_pressure", "кПа")),
    ("DESIGN_PRESSURE", ("design_pressure", None)),
    ("Operating Pressure [psig]", ("operating_pressure", "psig")),
    ("Design\nTemperature (°C)", ("design_temperature", "°C")),
    ("Tag No.", ("tag", None)), ("Line No", ("tag", None)), ("Item", ("tag", None)),
    ("Material", ("material", None)), ("Pipe Class", ("pipe_class", None)),
    ("Quvur sinfi", ("pipe_class", None)), ("Motor Power, kW", ("power", "kW")),
    ("Size", ("size", None)), ("Fluid", ("fluid", None)), ("Среда", ("fluid", None)),
    ("Revision", ("revision", None)), ("Document No.", ("doc_number", None)),
    ("Remarks", None), ("", None), ("12", None),
])
def test_match_header(h, exp):
    assert match_header(h) == exp
