"""4-sikl yakuniy ko'rigida topilgan holatlar: taxmin fakt bo'lib ko'rinmasligi kerak."""
import pytest

from engcheck.core.models import DocType, Method, TagOccurrence
from engcheck.diagram import service as dg
from engcheck.diagram.edits import EditError, apply_edits, validate_op
from engcheck.diagram.generator import generate
from engcheck.diagram.svg import render_svg
from engcheck.ingest.extract import extract
from engcheck.ingest.headers import match_header
from engcheck.ingest.model import Cell, Page, ParsedDocument, Table

from ..review.factories import EQL, LL, PID, make_doc, make_param, make_tag


def _place(db, project, pid, tag, x, y, method=Method.cell):
    make_tag(db, project, pid, tag, method=method)
    occ = db.query(TagOccurrence).filter_by(document_id=pid.id).order_by(TagOccurrence.id.desc()).first()
    occ.location = f"x={float(x)},y={float(y)}"
    db.flush()


@pytest.fixture
def sheet(db, project):
    pid = make_doc(db, project, PID)
    for tag, x, y in (("V-101", 40, 120), ("V-102", 100, 120), ("E-101", 400, 60), ("P-101A", 420, 300)):
        _place(db, project, pid, tag, x, y)
    return pid


# 1 — hujjatda bir uchi yozilgan bo'lsa, taxmin uni bekor qilmaydi
def test_partial_from_to_is_never_overridden_by_inference(db, project, sheet):
    ll = make_doc(db, project, LL)
    make_param(db, project, ll, '6"-AM-1003-B1A', "line_from", "P-101A")
    _place(db, project, sheet, '6"-AM-1003-B1A', 70, 125, Method.regex)      # chizmada V-101 va V-102 orasida
    g = generate(db, project.id)
    assert g["edges"] == [] and g["unconnected"] == ['6"-AM-1003-B1A (P-101A → ?)']


def test_same_from_and_to_is_unconnected(db, project):
    ll = make_doc(db, project, LL)
    make_param(db, project, ll, '6"-AM-1003-B1A', "line_from", "V-101")
    make_param(db, project, ll, '6"-AM-1003-B1A', "line_to", "V-101")
    assert generate(db, project.id)["unconnected"] == ['6"-AM-1003-B1A (V-101 → V-101)']


# 2 — "eng yaqin ikki uskuna" faqat aniq holatda
def test_far_away_line_label_is_not_connected(db, project, sheet):
    _place(db, project, sheet, '6"-AM-1003-B1A', 900000, 900000, Method.regex)
    g = generate(db, project.id)
    assert g["edges"] == [] and g["unconnected"] == ['6"-AM-1003-B1A']


def test_ambiguous_third_candidate_blocks_inference(db, project, sheet):
    _place(db, project, sheet, "V-103", 70, 95)                               # uchinchi uskuna deyarli bir xil masofada
    _place(db, project, sheet, '6"-AM-1003-B1A', 70, 125, Method.regex)
    assert generate(db, project.id)["edges"] == []


def test_two_equipment_only_sheet_never_infers(db, project):
    pid = make_doc(db, project, PID)
    _place(db, project, pid, "V-101", 40, 120); _place(db, project, pid, "V-102", 100, 120)
    _place(db, project, pid, '6"-AM-1003-B1A', 70, 125, Method.regex)
    assert generate(db, project.id)["edges"] == []


# 3 — taxminiy ulanishning yo'nalishi yo'q
def test_inferred_edge_is_undirected_document_edge_is_directed(db, project, sheet):
    _place(db, project, sheet, '6"-AM-1003-B1A', 70, 125, Method.regex)
    ll = make_doc(db, project, LL)
    make_param(db, project, ll, '8"-AM-1002-A1A', "line_from", "P-101A"); make_param(db, project, ll, '8"-AM-1002-A1A', "line_to", "V-101")
    edges = {e["source"]: e for e in generate(db, project.id)["edges"]}
    assert edges["inferred"]["directed"] is False and edges["document"]["directed"] is True
    svg = render_svg({"nodes": generate(db, project.id)["nodes"], "edges": list(edges.values()), "differences": []})
    assert svg.count('marker-end') == 1                                        # o'q uchi faqat hujjatdagi ulanishda


# 4, 5 — nomi o'zgartirilgan uskuna va eksportdagi izohlar
def test_renamed_document_node_is_marked_and_keeps_original_in_export(db, project, sheet):
    g = generate(db, project.id)
    d, _ = apply_edits(g, [{"op": "rename_node", "id": "eq:V-101", "label": "V-999"}])
    node = next(n for n in d["nodes"] if n["id"] == "eq:V-101")
    assert node["renamed"] is True and node["original_label"] == "V-101"
    svg = render_svg({**d, "differences": [{"kind": "node_renamed", "label": "V-101 → V-999"}]})
    assert "V-999" in svg and "V-101" in svg and 'data-renamed="true"' in svg


def test_svg_export_carries_legend_and_disclaimer(db, project, sheet):
    svg = render_svg({**generate(db, project.id), "differences": []}, locale="en")
    for text in ("From documents", "Inferred", "Added manually", "does not replace the P&amp;ID"):
        assert text in svg
    assert "Hujjatdan" in render_svg({**generate(db, project.id), "differences": []}, locale="uz")


# 7, 11, 12 — tahrirlarni tekshirish
@pytest.mark.parametrize("op", [
    {"op": "move", "id": "eq:V-101", "x": 10 ** 400, "y": 1},
    {"op": "add_node", "id": "m:1", "label": "V‮101", "kind": "vessel", "x": 1, "y": 1},     # yo'nalishni teskari qiluvchi belgi
    {"op": "add_node", "id": "m:1", "label": "V\x7f101", "kind": "vessel", "x": 1, "y": 1},
    {"op": "add_node", "id": "m:1", "label": "B.L.", "kind": "boundary", "x": 1, "y": 1},
    {"op": "rename_node", "id": "eq:V-101", "label": "a​b"},
])
def test_more_invalid_ops(op):
    with pytest.raises(EditError):
        validate_op(op)


def test_duplicate_manual_edge_between_same_pair_is_refused(db, project, sheet):
    ll = make_doc(db, project, LL)
    make_param(db, project, ll, '8"-AM-1002-A1A', "line_from", "P-101A"); make_param(db, project, ll, '8"-AM-1002-A1A', "line_to", "V-101")
    dg.regenerate(db, project.id, None)
    with pytest.raises(EditError):
        dg.add_edit(db, project.id, None, {"op": "add_edge", "id": "m:1", "from": "eq:P-101A", "to": "eq:V-101", "label": ""})
    dg.add_edit(db, project.id, None, {"op": "add_edge", "id": "m:2", "from": "eq:V-101", "to": "eq:P-101A", "label": ""})   # teskari yo'nalish — boshqa ulanish


# 9 — faqat quvurlar ro'yxatida uchragan uskuna alohida belgilanadi
def test_equipment_known_only_from_line_list_is_flagged(db, project):
    eql, ll = make_doc(db, project, EQL), make_doc(db, project, LL)
    make_param(db, project, eql, "V-101", "material", "CS")
    make_param(db, project, ll, '6"-AM-1003-B1A', "line_from", "V-101"); make_param(db, project, ll, '6"-AM-1003-B1A', "line_to", "V-9O1")
    nodes = {n["id"]: n for n in generate(db, project.id)["nodes"]}
    assert nodes["eq:V-101"].get("line_list_only") is not True
    typo = next(n for n in nodes.values() if n["id"] != "eq:V-101")
    assert typo["kind"] == "boundary"          # "V-9O1" teg emas (raqam o'rnida harf): chegara tuguni
    make_param(db, project, ll, '8"-AM-1002-A1A', "line_from", "V-101"); make_param(db, project, ll, '8"-AM-1002-A1A', "line_to", "V-901")
    assert next(n for n in generate(db, project.id)["nodes"] if n["id"] == "eq:V-901")["line_list_only"] is True


# 10 — From/To faqat quvurlar ro'yxatida
def test_from_to_headers_only_apply_to_line_lists():
    assert match_header("From") == ("line_from", None) and match_header("To") == ("line_to", None)
    for generic in ("dan", "ga", "от", "до"):
        assert match_header(generic) is None
    t = Table([[Cell(v, f"S!{chr(65 + c)}{r + 1}") for c, v in enumerate(row)] for r, row in enumerate(
        [["Item", "From", "To"], ["V-101", "Client", "Vendor"]])])
    ex = extract(ParsedDocument([Page(1, "", [t])]), DocType.OTHER)
    assert ex.params == []          # jadval quvurlar ro'yxati emas: From/To parametr sifatida olinmaydi
    ex = extract(ParsedDocument([Page(1, "", [Table([[Cell("Line No", "a"), Cell("From", "b"), Cell("To", "c")],
                                                      [Cell('6"-AM-1003-B1A', "a2"), Cell("V-101", "b2"), Cell("V-102", "c2")]])])]), DocType.LINE_LIST)
    assert {p.param for p in ex.params} == {"line_from", "line_to"}
