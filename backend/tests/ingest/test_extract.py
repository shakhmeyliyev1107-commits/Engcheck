from engcheck.core.models import Confidence, DocType, Method, TagClass
from engcheck.ingest.extract import extract
from engcheck.ingest.model import Cell, Page, ParsedDocument, Table, TextItem


def table(rows, prefix="S!"):
    return Table([[Cell(v, f"{prefix}{chr(65 + c)}{r + 1}") for c, v in enumerate(row)]
                  for r, row in enumerate(rows)])


def doc(*tables, text="", items=None):
    return ParsedDocument([Page(number=1, text=text, tables=list(tables), items=items or [])])


def by(ex, tag, param):
    return next(p for p in ex.params if p.tag == tag and p.param == param)


def test_columnar_table_with_title_rows():
    t = table([
        ["EQUIPMENT LIST", "", "", ""],
        ["Project: Gas plant", "", "", ""],
        ["", "", "", ""],
        ["Tag No.", "Design Pressure, barg", "Material", "Remarks"],
        ["V-101", "16", "CS", "note"],
        ["p-101 a", "10,5", "SS316", ""],
    ])
    ex = extract(doc(t), DocType.EQUIPMENT_LIST)
    assert [(x.tag, x.tag_class, x.method) for x in ex.tags] == [
        ("V-101", TagClass.equipment, Method.cell), ("P-101A", TagClass.equipment, Method.cell)]
    p = by(ex, "V-101", "design_pressure")
    assert p.si_value == 1600.0 and p.location == "S!B5" and p.raw_unit == "barg"
    assert p.method == Method.cell and p.confidence == Confidence.high and p.page_no == 1
    assert by(ex, "P-101A", "design_pressure").si_value == 1050.0
    assert by(ex, "P-101A", "material").raw_value == "SS316"


def test_header_beyond_15_rows_not_treated_as_table():
    rows = [["x", "y"]] * 16 + [["Tag No.", "Material"], ["V-101", "CS"]]
    ex = extract(doc(table(rows)), DocType.EQUIPMENT_LIST)
    assert ex.params == []


def test_unmapped_headers_reported():
    t = table([["Tag No.", "Material", "Remarks", "Vendor"], ["V-101", "CS", "a", "b"]])
    assert extract(doc(t), DocType.EQUIPMENT_LIST).unmapped_headers == ["Remarks", "Vendor"]


def test_empty_cell_and_dash_yield_no_param():
    t = table([["Tag No.", "Material", "Power, kW"], ["P-101B", "", "-"]])
    ex = extract(doc(t), DocType.EQUIPMENT_LIST)
    assert [x.tag for x in ex.tags] == ["P-101B"] and ex.params == []


def test_rows_without_valid_tag_skipped():
    t = table([["Tag No.", "Material"], ["Total", "CS"], ["", "CS"], ["V-101", "CS"]])
    assert [x.tag for x in extract(doc(t), DocType.EQUIPMENT_LIST).tags] == ["V-101"]


def test_key_value_datasheet_with_unit_column():
    t = table([
        ["Tag No", "V-101", ""],
        ["Design Pressure", "10", "barg"],
        ["Operating Pressure", "174 psig", ""],
        ["Material", "CS", ""],
        ["Vendor", "ACME", ""],
    ], prefix="t1:")
    ex = extract(doc(t), DocType.DATASHEET)
    assert [(x.tag, x.method) for x in ex.tags] == [("V-101", Method.cell)]
    p = by(ex, "V-101", "design_pressure")
    assert p.si_value == 1000.0 and p.method == Method.cell and p.confidence == Confidence.high
    assert abs(by(ex, "V-101", "operating_pressure").si_value - 1199.69) < 0.1
    assert "Vendor" in ex.unmapped_headers


def test_key_value_two_columns():
    t = table([["Tag No", "P-101A"], ["Motor Power", "55 kW"], ["Material", "SS316"]])
    assert by(extract(doc(t), DocType.DATASHEET), "P-101A", "power").si_value == 55.0


def test_key_value_doc_number_and_revision():
    t = table([["Document No.", "GP-DS-V101"], ["Revision", "A"], ["Tag No", "V-101"],
               ["Material", "CS"]])
    ex = extract(doc(t), DocType.DATASHEET)
    assert ex.doc_number == "GP-DS-V101" and ex.revision == "A"


def test_free_text_gives_tags_only():
    ex = extract(doc(text="Pump P-101A design pressure 16 barg", items=[
        TextItem("Pump P-101A design pressure 16 barg", "para1")]), DocType.OTHER)
    assert [(x.tag, x.method, x.location) for x in ex.tags] == [("P-101A", Method.regex, "para1")]
    assert ex.params == []


def test_tag_found_in_cell_not_duplicated_from_page_text():
    t = table([["Tag No.", "Material"], ["V-101", "CS"]])
    ex = extract(doc(t, text="Tag No. Material\nV-101 CS\nSee also E-102"), DocType.EQUIPMENT_LIST)
    assert sorted((x.tag, x.method) for x in ex.tags) == [("E-102", Method.regex), ("V-101", Method.cell)]


def test_dxf_block_attributes_are_cells():
    items = [TextItem("VESSEL", "x=100.0,y=50.0", {"TAG": "V-101", "DESIGN_PRESSURE": "16 barg",
                                                    "DESIGN_TEMPERATURE": "120 °C"}),
             TextItem('10"-HC-1001-A1A', "x=1.0,y=2.0")]
    ex = extract(doc(items=items), DocType.PID)
    p = by(ex, "V-101", "design_pressure")
    assert p.si_value == 1600.0 and p.method == Method.cell and p.location == "x=100.0,y=50.0"
    assert ('10"-HC-1001-A1A', TagClass.line, Method.regex) in [(x.tag, x.tag_class, x.method) for x in ex.tags]


def test_refs_extracted():
    ex = extract(doc(text="Ref. P&ID GP-PID-001 Rev A\nsee GP-EQL-001, Rev. B"), DocType.DATASHEET)
    assert ex.refs == [("GP-PID-001", "A", 1), ("GP-EQL-001", "B", 1)]


def test_material_spec_pipe_classes():
    t = table([["Pipe Class", "Material", "Rating"], ["A1A", "CS", "150#"], ["b1a", "SS", "150#"]])
    ex = extract(doc(t), DocType.MATERIAL_SPEC)
    assert [(x.tag, x.tag_class) for x in ex.tags] == [("A1A", TagClass.pipe_class), ("B1A", TagClass.pipe_class)]


def test_line_list_pipe_class_is_param_not_tag():
    t = table([["Line No", "Size", "Pipe Class", "Fluid"], ['6"-AM-1004-A1A', '6"', "A1A", "Amine"]])
    ex = extract(doc(t), DocType.LINE_LIST)
    assert [x.tag_class for x in ex.tags] == [TagClass.line]
    assert by(ex, '6"-AM-1004-A1A', "pipe_class").raw_value == "A1A"
    assert by(ex, '6"-AM-1004-A1A', "size").si_value == 152.4


def test_assumed_unit_lowers_confidence():
    t = table([["Tag No.", "Design Pressure"], ["V-101", "16 bar"]])
    assert by(extract(doc(t), DocType.EQUIPMENT_LIST), "V-101", "design_pressure").confidence == Confidence.medium


def test_unknown_unit_kept_with_flag():
    t = table([["Tag No.", "Design Pressure"], ["V-101", "16"]])
    p = by(extract(doc(t), DocType.EQUIPMENT_LIST), "V-101", "design_pressure")
    assert p.number == 16 and p.si_value is None and p.unit_known is False


def test_multiple_pages_keep_page_numbers():
    t1 = table([["Tag No", "P-101A"], ["Motor Power", "55 kW"]])
    t2 = table([["Tag No", "P-101B"], ["Motor Power", "45 kW"]])
    d = ParsedDocument([Page(1, "", [t1]), Page(2, "", [t2])])
    ex = extract(d, DocType.DATASHEET)
    assert by(ex, "P-101B", "power").page_no == 2


def test_length_and_height_columns_are_equipment_dimensions_only_in_equipment_documents():
    line = table([["Line No", "Size", "Length", "Fluid"], ['6"-AM-1004-A1A', '6"', "120", "Amine"]])
    ex = extract(doc(line), DocType.LINE_LIST)
    assert {p.param for p in ex.params} == {"size", "fluid"} and "Length" in ex.unmapped_headers   # quvur uzunligi gabarit emas
    eq = table([["Tag No.", "Height, mm", "Length, mm"], ["V-101", "9000", "3000"]])
    ex = extract(doc(eq), DocType.EQUIPMENT_LIST)
    assert by(ex, "V-101", "equipment_height").si_value == 9000.0 and by(ex, "V-101", "equipment_length").si_value == 3000.0
    kv = table([["Tag No.", "V-101"], ["Material", "CS"], ["Height", "9000 mm"]])
    assert "equipment_height" not in {p.param for p in extract(doc(kv), DocType.CALCULATION).params}
    assert by(extract(doc(kv), DocType.DATASHEET), "V-101", "equipment_height").si_value == 9000.0
