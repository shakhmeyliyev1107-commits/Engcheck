import ezdxf
import openpyxl
import pytest
from docx import Document as Docx
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table as RlTable, TableStyle

from engcheck.ingest.detect import detect_format
from engcheck.ingest.parsers import ParseError, parse_file


def _pdf_with_table(path, rows):
    t = RlTable(rows)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, (0, 0, 0))]))
    SimpleDocTemplate(str(path), pagesize=A4).build([t])


def test_xlsx_cells_and_location(tmp_path):
    p = tmp_path / "a.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "List"
    ws.append(["Tag", "Design Pressure, barg"])
    ws.append(["V-101", 16])
    wb.save(p)
    doc = parse_file(p)
    assert len(doc.pages) == 1 and doc.pages[0].number == 1
    rows = doc.pages[0].tables[0].rows
    assert rows[1][0].text == "V-101"
    assert rows[1][1].text == "16" and rows[1][1].location == "List!B2"


def test_xlsx_float_keeps_decimals_and_int_has_no_dot_zero(tmp_path):
    p = tmp_path / "a.xlsx"
    wb = openpyxl.Workbook()
    wb.active.append([10.5, 16.0])
    wb.save(p)
    rows = parse_file(p).pages[0].tables[0].rows
    assert [c.text for c in rows[0]] == ["10.5", "16"]


def test_xlsx_merged_title_row(tmp_path):
    p = tmp_path / "a.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "EQUIPMENT LIST"
    ws.merge_cells("A1:D1")
    ws.append(["Tag", "Material", "x", "y"])
    wb.save(p)
    rows = parse_file(p).pages[0].tables[0].rows
    assert rows[0][0].text == "EQUIPMENT LIST"
    assert [c.text for c in rows[0][1:]] == ["", "", ""]


def test_xlsx_each_sheet_is_a_page(tmp_path):
    p = tmp_path / "a.xlsx"
    wb = openpyxl.Workbook()
    wb.active.append(["a"])
    wb.create_sheet("Two").append(["b"])
    wb.save(p)
    doc = parse_file(p)
    assert [pg.number for pg in doc.pages] == [1, 2]
    assert doc.pages[1].tables[0].rows[0][0].location == "Two!A1"


def test_pdf_table_extracted(tmp_path):
    p = tmp_path / "a.pdf"
    _pdf_with_table(p, [["Tag No", "V-101"], ["Design Pressure", "10 barg"]])
    doc = parse_file(p)
    cell = doc.pages[0].tables[0].rows[1][1]
    assert cell.text == "10 barg" and cell.location == "t1:r2:c2"
    assert "V-101" in doc.pages[0].text


def test_pdf_without_text_needs_ocr(tmp_path):
    p = tmp_path / "scan.pdf"
    c = canvas.Canvas(str(p), pagesize=A4)
    c.rect(50, 50, 200, 200)
    c.save()
    with pytest.raises(ParseError) as e:
        parse_file(p)
    assert e.value.code == "needs_ocr"


def test_docx_table_and_paragraph(tmp_path):
    p = tmp_path / "a.docx"
    d = Docx()
    d.add_paragraph("Piping material specification GP-MS-001")
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text, t.cell(0, 1).text = "Pipe Class", "Material"
    t.cell(1, 0).text, t.cell(1, 1).text = "A1A", "CS"
    d.save(p)
    doc = parse_file(p)
    page = doc.pages[0]
    assert page.items[0].text.startswith("Piping material") and page.items[0].location == "para1"
    assert page.tables[0].rows[1][0].text == "A1A"
    assert page.tables[0].rows[1][0].location == "table1:r2:c1"
    assert "A1A" in page.text


def test_dxf_text_and_block_attrs(tmp_path):
    p = tmp_path / "a.dxf"
    d = ezdxf.new()
    blk = d.blocks.new("VESSEL")
    blk.add_attdef("TAG", (0, 0))
    blk.add_attdef("DESIGN_PRESSURE", (0, -5))
    msp = d.modelspace()
    msp.add_blockref("VESSEL", (100, 50)).add_auto_attribs({"TAG": "V-101", "DESIGN_PRESSURE": "16 barg"})
    msp.add_text('10"-HC-1001-A1A', dxfattribs={"insert": (120.5, 88)})
    msp.add_mtext("Ref: GP-PID-001 Rev C", dxfattribs={"insert": (10, 10)})
    d.saveas(p)
    page = parse_file(p).pages[0]
    blocks = [i for i in page.items if i.attrs]
    assert blocks[0].attrs == {"TAG": "V-101", "DESIGN_PRESSURE": "16 barg"}
    assert blocks[0].text == "VESSEL" and blocks[0].location == "x=100.0,y=50.0"
    texts = {i.text: i.location for i in page.items if not i.attrs}
    assert texts['10"-HC-1001-A1A'] == "x=120.5,y=88.0"
    assert "Ref: GP-PID-001 Rev C" in texts


def test_dwg_rejected(tmp_path):
    p = tmp_path / "a.dwg"
    p.write_bytes(b"AC1032" + b"\0" * 200)
    assert detect_format(p) == "dwg"
    with pytest.raises(ParseError) as e:
        parse_file(p)
    assert e.value.code == "unsupported_dwg"


def test_empty_file_is_corrupt(tmp_path):
    p = tmp_path / "a.pdf"
    p.write_bytes(b"")
    with pytest.raises(ParseError) as e:
        parse_file(p)
    assert e.value.code == "corrupt"


def test_pdf_named_xlsx_parsed_by_signature(tmp_path):
    p = tmp_path / "wrong.xlsx"
    _pdf_with_table(p, [["Tag No", "V-101"]])
    assert detect_format(p) == "pdf"
    assert "V-101" in parse_file(p).pages[0].text


def test_truncated_xlsx_is_corrupt(tmp_path):
    src = tmp_path / "a.xlsx"
    wb = openpyxl.Workbook()
    wb.active.append(["x"])
    wb.save(src)
    p = tmp_path / "cut.xlsx"
    p.write_bytes(src.read_bytes()[:200])
    with pytest.raises(ParseError) as e:
        parse_file(p)
    assert e.value.code == "corrupt"


def test_unknown_format(tmp_path):
    p = tmp_path / "a.bin"
    p.write_bytes(b"\x01\x02\x03 nothing useful here")
    with pytest.raises(ParseError) as e:
        parse_file(p)
    assert e.value.code == "unknown_format"


def test_garbage_named_pdf_is_corrupt(tmp_path):
    p = tmp_path / "a.pdf"
    p.write_bytes(b"%PDF-1.4 this is not really a pdf")
    with pytest.raises(ParseError) as e:
        parse_file(p)
    assert e.value.code == "corrupt"
