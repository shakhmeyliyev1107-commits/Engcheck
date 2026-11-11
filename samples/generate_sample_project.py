"""Namunaviy sanoat loyihasi: amin bilan gaz tozalash bloki.

Hujjatlarga tekshiruv dvigatelini sinash uchun ATAYLAB xatolar kiritilgan
(ro'yxat: docs/superpowers/specs, 10-bo'lim). Haqiqiy loyiha ma'lumoti emas.

Ishlatish:  python samples/generate_sample_project.py <papka>
"""
import sys
from dataclasses import dataclass
from pathlib import Path

import ezdxf
import openpyxl
from docx import Document as Docx
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from engcheck.core.models import Discipline, DocType


@dataclass
class SampleDoc:
    path: Path
    doc_type: DocType
    discipline: Discipline
    doc_number: str
    revision: str


def _pid(path: Path) -> None:
    doc = ezdxf.new("R2010")
    block = doc.blocks.new("EQUIPMENT")
    block.add_lwpolyline([(-10, -10), (10, -10), (10, 10), (-10, 10)], close=True)
    for i, name in enumerate(("TAG", "DESIGN_PRESSURE", "DESIGN_TEMPERATURE")):
        block.add_attdef(name, (-8, 4 - 5 * i), dxfattribs={"height": 2.5})
    msp = doc.modelspace()
    equipment = [
        ((40, 120), {"TAG": "V-101", "DESIGN_PRESSURE": "16 barg", "DESIGN_TEMPERATURE": "120 °C"}),
        ((100, 120), {"TAG": "V-102", "DESIGN_PRESSURE": "5 barg"}),
        ((40, 60), {"TAG": "P-101A"}),
        ((70, 60), {"TAG": "P-101B"}),
        ((130, 60), {"TAG": "E-101"}),
        ((160, 60), {"TAG": "E-102"}),   # ataylab: uskunalar ro'yxatida yo'q
    ]
    for insert, attrs in equipment:
        msp.add_blockref("EQUIPMENT", insert).add_auto_attribs(attrs)
    lines = [((20, 140), '10"-HC-1001-A1A'), ((60, 140), '8"-AM-1002-A1A'),
             ((100, 90), '6"-AM-1003-B1A'), ((140, 90), '4"-AM-1005-B2C')]
    for (x, y), number in lines:
        msp.add_line((x, y - 3), (x + 30, y - 3))
        msp.add_text(number, dxfattribs={"insert": (x, y), "height": 2.5})
    for (x, y), tag in [((45, 135), "PT-1001"), ((75, 75), "FIC-2003")]:
        msp.add_circle((x, y), 4)
        msp.add_text(tag, dxfattribs={"insert": (x - 3, y), "height": 2})
    msp.add_mtext("AMINE TREATING UNIT - P&ID\nGP-PID-001 Rev C", dxfattribs={"insert": (150, 20)})
    doc.saveas(path)


def _equipment_list(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Equipment"
    ws["A1"] = "EQUIPMENT LIST - AMINE TREATING UNIT"
    ws.merge_cells("A1:H1")
    ws["A2"] = "Document No: GP-EQL-001 Rev B"
    ws.append([])
    ws.append(["Tag No.", "Description", "Design Pressure, barg", "Operating Pressure, barg",
               "Design Temperature, °C", "Operating Temperature, °C", "Material", "Motor Power, kW"])
    rows = [
        ["V-101", "Amine Contactor", 16, 12, 120, 60, "CS", None],
        ["V-102", "Rich Amine Flash Drum", 5, 7, 120, 60, "CS", None],  # ataylab: loyiha < ish bosimi
        ["P-101A", "Lean Amine Pump", 20, 15, 120, 60, "SS316", 45],    # ataylab: datasheetda 55 kW
        ["P-101B", "Lean Amine Pump (spare)", 20, 15, 120, 60, "SS316", 45],
        ["E-101", "Lean/Rich Amine Exchanger", 16, 12, 150, 110, "CS", None],
    ]
    for row in rows:
        ws.append(row)
    wb.save(path)


def _line_list(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Lines"
    ws["A1"] = "LINE LIST - AMINE TREATING UNIT"
    ws["A2"] = "Document No: GP-LL-001 Rev B"
    ws.append([])
    ws.append(["Line No", "Size", "Fluid", "Pipe Class", "Design Pressure, barg",
               "Design Temperature, °C", "From", "To"])
    rows = [
        ['10"-HC-1001-A1A', '10"', "Sour Gas", "A1A", 16, 120, "B.L.", "V-101"],
        ['8"-AM-1002-A1A', '8"', "Lean Amine", "A1A", 16, 120, "P-101A", "V-101"],
        ['6"-AM-1003-B1A', '6"', "Rich Amine", "B1A", 16, 120, "V-101", "V-102"],
        ['6"-AM-1004-A1A', '6"', "Lean Amine", "A1A", 16, 120, "E-101", "P-101A"],   # ataylab: P&ID da yo'q
        ['4"-AM-1005-B2C', '4"', "Amine Drain", "B2C", 5, 120, "V-102", "Drain"],    # ataylab: B2C spetsifikatsiyada yo'q
    ]
    for row in rows:
        ws.append(row)
    wb.save(path)


_GRID = TableStyle([("GRID", (0, 0), (-1, -1), 0.5, (0, 0, 0)), ("FONTSIZE", (0, 0), (-1, -1), 10)])


def _datasheet_page(title: str, rows: list[list[str]], pid_rev: str) -> list:
    styles = getSampleStyleSheet()
    table = Table(rows, colWidths=[180, 220])
    table.setStyle(_GRID)
    return [Paragraph(title, styles["Heading2"]), Spacer(1, 8), table, Spacer(1, 12),
            Paragraph(f"Ref. P&amp;ID GP-PID-001 Rev {pid_rev}", styles["Normal"])]


def _datasheet_v101(path: Path) -> None:
    rows = [
        ["Document No.", "GP-DS-V101"], ["Revision", "A"], ["Tag No", "V-101"],
        ["Service", "Amine Contactor"],
        ["Design Pressure", "14 barg"],          # ataylab: P&ID va ro'yxatda 16 barg
        ["Operating Pressure", "174 psig"],      # 12 barg ga teng — topilma bo'lmasligi kerak
        ["Design Temperature", "120 °C"], ["Operating Temperature", "60 °C"],
        ["Material", "CS"],
    ]
    # ataylab: P&ID ning eskirgan Rev A siga havola (joriy Rev C)
    SimpleDocTemplate(str(path), pagesize=A4).build(
        _datasheet_page("PRESSURE VESSEL DATA SHEET", rows, "A"))


def _datasheet_p101(path: Path) -> None:
    def rows(tag: str, power: str, material: str) -> list[list[str]]:
        return [["Document No.", "GP-DS-P101"], ["Revision", "A"], ["Tag No", tag],
                ["Service", "Lean Amine Pump"], ["Design Pressure", "20 barg"],
                ["Design Temperature", "120 °C"], ["Motor Power", power], ["Material", material]]

    story = _datasheet_page("CENTRIFUGAL PUMP DATA SHEET", rows("P-101A", "55 kW", "SS316"), "C")
    story.append(PageBreak())
    # ataylab: P-101B materiali bo'sh
    story += _datasheet_page("CENTRIFUGAL PUMP DATA SHEET", rows("P-101B", "45 kW", ""), "C")
    SimpleDocTemplate(str(path), pagesize=A4).build(story)


def _material_spec(path: Path) -> None:
    d = Docx()
    d.add_heading("Piping Material Specification", level=1)
    d.add_paragraph("Document No: GP-MS-001 Rev A")
    d.add_paragraph("Pipe classes applicable to the Amine Treating Unit.")
    rows = [["Pipe Class", "Material", "Rating", "Corrosion Allowance, mm"],
            ["A1A", "Carbon Steel A106 Gr.B", "150#", "3"],
            ["B1A", "Stainless Steel A312 TP316L", "150#", "0"]]
    t = d.add_table(rows=len(rows), cols=4)
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            t.cell(r, c).text = value
    d.save(path)


def plot_plan(path: Path) -> SampleDoc:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return _plot_plan(Path(path))


def _plot_plan(path: Path) -> SampleDoc:
    """Bosh reja (civil): uskunalar joylashuvi, birlik — millimetr. Asosiy 6 hujjatga kirmaydi; alohida yuklanadi."""
    doc = ezdxf.new("R2010")
    block = doc.blocks.new("EQUIPMENT")
    block.add_circle((0, 0), 1000)
    block.add_attdef("TAG", (-800, 0), dxfattribs={"height": 400})
    msp = doc.modelspace()
    for tag, (x, y) in {"V-101": (10000, 20000), "V-102": (22000, 20000), "P-101A": (10000, 8000),
                        "P-101B": (13000, 8000), "E-101": (22000, 8000)}.items():
        msp.add_blockref("EQUIPMENT", (x, y)).add_auto_attribs({"TAG": tag})
    msp.add_mtext("PLOT PLAN - AMINE TREATING UNIT\nGP-PLT-001 Rev A", dxfattribs={"insert": (30000, 2000)})
    doc.saveas(path)
    return SampleDoc(path, DocType.OTHER, Discipline.civil, "GP-PLT-001", "A")


def generate(out_dir: Path) -> list[SampleDoc]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    spec = [
        ("GP-PID-001_RevC.dxf", _pid, DocType.PID, Discipline.process, "GP-PID-001", "C"),
        ("GP-EQL-001_RevB.xlsx", _equipment_list, DocType.EQUIPMENT_LIST, Discipline.mechanical, "GP-EQL-001", "B"),
        ("GP-LL-001_RevB.xlsx", _line_list, DocType.LINE_LIST, Discipline.piping, "GP-LL-001", "B"),
        ("GP-DS-V101_RevA.pdf", _datasheet_v101, DocType.DATASHEET, Discipline.mechanical, "GP-DS-V101", "A"),
        ("GP-DS-P101_RevA.pdf", _datasheet_p101, DocType.DATASHEET, Discipline.mechanical, "GP-DS-P101", "A"),
        ("GP-MS-001_RevA.docx", _material_spec, DocType.MATERIAL_SPEC, Discipline.piping, "GP-MS-001", "A"),
    ]
    docs = []
    for name, build, doc_type, discipline, number, rev in spec:
        build(out / name)
        docs.append(SampleDoc(out / name, doc_type, discipline, number, rev))
    return docs


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "sample_project")
    for doc in generate(target):
        print(f"{doc.doc_type.value:15} {doc.path}")
    # --plot-plan: bosh reja chizmasini alohida papkaga yozadi (asosiy 6 hujjat to'plamini o'zgartirmaydi)
    extra = plot_plan(Path(str(target) + "_extra") / "GP-PLT-001_RevA.dxf") if "--plot-plan" in sys.argv else None
    if extra:
        print(f"{'PLOT PLAN':15} {extra.path}  (intizom: civil; alohida yuklang)")
