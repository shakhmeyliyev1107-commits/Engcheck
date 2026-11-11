import math

import pytest

from engcheck.core.auth import create_user
from engcheck.core.models import AuditLog, DiagramEdit, Method, TagOccurrence
from engcheck.diagram import service as dg
from engcheck.diagram.edits import EditError, apply_edits, validate_op
from engcheck.diagram.generator import generate, node_kind
from engcheck.diagram.layout import layout
from engcheck.diagram.svg import render_svg

from ..review.factories import EQL, LL, PID, make_doc, make_param, make_tag


@pytest.fixture
def user(db):
    return create_user(db, "aziz", "S3cret-pass", "engineer")


@pytest.fixture
def plant(db, project):
    """V-101 → (6"-AM-1003) → V-102; P-101A → (8"-AM-1002) → V-101; B.L. → (10"-HC-1001) → V-101."""
    eql, ll = make_doc(db, project, EQL, "GP-EQL-001"), make_doc(db, project, LL, "GP-LL-001")
    for tag in ("V-101", "V-102", "P-101A", "E-101"):
        make_param(db, project, eql, tag, "material", "CS")
    make_param(db, project, eql, "V-101", "design_pressure", "16 barg", 1600.0)
    for line, src, dst in (('6"-AM-1003-B1A', "V-101", "V-102"), ('8"-AM-1002-A1A', "p-101 a", "V-101"),
                           ('10"-HC-1001-A1A', "B.L.", "V-101")):
        make_param(db, project, ll, line, "line_from", src)
        make_param(db, project, ll, line, "line_to", dst)
    make_param(db, project, ll, '4"-AM-1005-B2C', "size", '4"', 101.6)       # uchi ko'rsatilmagan quvur
    return project


def _ids(items):
    return sorted(i["id"] for i in items)


@pytest.mark.parametrize("tag,kind", [("V-101", "vessel"), ("P-101A", "pump"), ("E-101", "exchanger"), ("T-201", "column"),
                                      ("C-201", "column"), ("K-301", "compressor"), ("TK-401", "tank"), ("R-501", "reactor"),
                                      ("XX-999", "generic"), ("10-P-101A", "pump")])
def test_node_kind_from_prefix(tag, kind):
    assert node_kind(tag) == kind


def test_generate_nodes_edges_boundary_and_unconnected(db, plant):
    g = generate(db, plant.id)
    assert _ids(g["nodes"]) == ["bd:B.L.", "eq:E-101", "eq:P-101A", "eq:V-101", "eq:V-102"]
    edges = {e["id"]: (e["from"], e["to"], e["source"]) for e in g["edges"]}
    assert edges == {'ln:6"-AM-1003-B1A': ("eq:V-101", "eq:V-102", "document"),
                     'ln:8"-AM-1002-A1A': ("eq:P-101A", "eq:V-101", "document"),      # "p-101 a" kanonik tegga keltirildi
                     'ln:10"-HC-1001-A1A': ("bd:B.L.", "eq:V-101", "document")}
    assert g["unconnected"] == ['4"-AM-1005-B2C']
    v101 = next(n for n in g["nodes"] if n["id"] == "eq:V-101")
    assert (v101["kind"], v101["source"], v101["label"]) == ("vessel", "document", "V-101")
    assert v101["params"]["design_pressure"] == "16 barg"
    assert next(n for n in g["nodes"] if n["id"] == "bd:B.L.")["kind"] == "boundary"


def test_endpoint_tag_not_in_equipment_docs_still_becomes_a_node(db, project):
    ll = make_doc(db, project, LL)
    make_param(db, project, ll, '6"-AM-1003-B1A', "line_from", "V-900")
    make_param(db, project, ll, '6"-AM-1003-B1A', "line_to", "V-901")
    g = generate(db, project.id)
    assert _ids(g["nodes"]) == ["eq:V-900", "eq:V-901"] and g["edges"][0]["source"] == "document"


def test_connection_inferred_from_dxf_geometry_is_marked(db, project):
    pid = make_doc(db, project, PID)
    for tag, loc in (("V-101", "x=40.0,y=120.0"), ("V-102", "x=100.0,y=120.0"), ("E-101", "x=400.0,y=60.0")):
        make_tag(db, project, pid, tag)
        db.query(TagOccurrence).filter_by(document_id=pid.id).order_by(TagOccurrence.id.desc()).first().location = loc
    make_tag(db, project, pid, '6"-AM-1003-B1A', method=Method.regex)
    db.query(TagOccurrence).filter_by(document_id=pid.id).order_by(TagOccurrence.id.desc()).first().location = "x=70.0,y=125.0"
    db.flush()
    (edge,) = generate(db, project.id)["edges"]
    assert edge["source"] == "inferred" and {edge["from"], edge["to"]} == {"eq:V-101", "eq:V-102"}


def test_superseded_documents_are_ignored(db, project):
    old, new = make_doc(db, project, EQL, "GP-EQL-001", "A"), make_doc(db, project, EQL, "GP-EQL-001", "B")
    make_param(db, project, old, "V-999", "material", "CS")
    make_param(db, project, new, "V-101", "material", "CS")
    assert _ids(generate(db, project.id)["nodes"]) == ["eq:V-101"]


def test_layout_is_deterministic_left_to_right_and_non_overlapping(db, plant):
    a, b = generate(db, plant.id), generate(db, plant.id)
    assert a == b
    pos = {n["id"]: (n["x"], n["y"]) for n in a["nodes"]}
    assert pos["eq:P-101A"][0] < pos["eq:V-101"][0] < pos["eq:V-102"][0]
    assert len(set(pos.values())) == len(pos) and all(math.isfinite(v) for p in pos.values() for v in p)


def test_layout_survives_cycles_and_isolated_nodes():
    nodes = [{"id": i} for i in "abcd"]
    edges = [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}, {"from": "b", "to": "c"}, {"from": "c", "to": "c"}]
    layout(nodes, edges)
    assert len({(n["x"], n["y"]) for n in nodes}) == 4


# ---------- tahrirlar ----------
def test_edits_apply_in_order(db, plant):
    g = generate(db, plant.id)
    ops = [{"op": "move", "id": "eq:V-101", "x": 500, "y": 300},
           {"op": "add_node", "id": "m:1", "label": "V-103", "kind": "vessel", "x": 10, "y": 20},
           {"op": "add_edge", "id": "m:2", "from": "eq:V-102", "to": "m:1", "label": "yangi"},
           {"op": "rename_node", "id": "eq:E-101", "label": "E-101 (yangi)"},
           {"op": "remove_node", "id": "eq:P-101A"}]
    d, skipped = apply_edits(g, ops)
    nodes = {n["id"]: n for n in d["nodes"]}
    assert skipped == [] and (nodes["eq:V-101"]["x"], nodes["eq:V-101"]["y"]) == (500, 300) and nodes["eq:V-101"]["moved"]
    assert nodes["m:1"]["source"] == "manual" and "eq:P-101A" not in nodes
    assert nodes["eq:E-101"]["label"] == "E-101 (yangi)" and nodes["eq:E-101"]["original_label"] == "E-101"
    edges = {e["id"]: e for e in d["edges"]}
    assert edges["m:2"]["source"] == "manual" and 'ln:8"-AM-1002-A1A' not in edges        # tugun bilan birga qirrasi ham ketdi
    assert g["nodes"] != d["nodes"] and "moved" not in next(n for n in g["nodes"] if n["id"] == "eq:V-101")  # asl qatlam o'zgarmadi


def test_edits_for_missing_elements_are_skipped_and_reported(db, plant):
    g = generate(db, plant.id)
    d, skipped = apply_edits(g, [{"op": "move", "id": "eq:YOQ", "x": 1, "y": 2},
                                 {"op": "add_edge", "id": "m:9", "from": "eq:V-101", "to": "eq:YOQ", "label": ""},
                                 {"op": "move", "id": "eq:V-102", "x": 7, "y": 8}])
    assert skipped == [0, 1] and next(n for n in d["nodes"] if n["id"] == "eq:V-102")["x"] == 7


@pytest.mark.parametrize("op", [
    {"op": "explode"}, {"op": "move", "id": "eq:V-101", "x": "a", "y": 1}, {"op": "move", "id": "eq:V-101", "x": float("nan"), "y": 1},
    {"op": "move", "id": "eq:V-101", "x": 1e9, "y": 1}, {"op": "add_node", "id": "eq:FAKE", "label": "x", "kind": "vessel", "x": 1, "y": 1},
    {"op": "add_node", "id": "m:1", "label": "", "kind": "vessel", "x": 1, "y": 1},
    {"op": "add_node", "id": "m:1", "label": "x" * 200, "kind": "vessel", "x": 1, "y": 1},
    {"op": "add_node", "id": "m:1", "label": "x", "kind": "spaceship", "x": 1, "y": 1},
    {"op": "add_edge", "id": "ln:FAKE", "from": "a", "to": "b", "label": ""}, {"op": "rename_node", "id": "eq:V-101", "label": ["x"]},
    {"op": "remove_node"}, "satr", None,
])
def test_invalid_ops_are_rejected(op):
    with pytest.raises(EditError):
        validate_op(op)


# ---------- xizmat: saqlash, undo/redo, qayta yaratish ----------
def test_service_generate_edit_undo_redo(db, plant, user):
    assert dg.get(db, plant.id)["exists"] is False
    dg.regenerate(db, plant.id, user)
    dg.add_edit(db, plant.id, user, {"op": "move", "id": "eq:V-101", "x": 500, "y": 300})
    dg.add_edit(db, plant.id, user, {"op": "add_node", "id": "m:1", "label": "V-103", "kind": "vessel", "x": 10, "y": 20})
    d = dg.get(db, plant.id)
    assert d["can_undo"] and not d["can_redo"] and "m:1" in _ids(d["nodes"])
    dg.undo(db, plant.id, user)
    d = dg.get(db, plant.id)
    assert "m:1" not in _ids(d["nodes"]) and d["can_redo"] and next(n for n in d["nodes"] if n["id"] == "eq:V-101")["x"] == 500
    dg.redo(db, plant.id, user)
    assert "m:1" in _ids(dg.get(db, plant.id)["nodes"])
    dg.undo(db, plant.id, user); dg.undo(db, plant.id, user)
    d = dg.get(db, plant.id)
    assert not d["can_undo"] and d["can_redo"] and next(n for n in d["nodes"] if n["id"] == "eq:V-101")["x"] != 500
    with pytest.raises(EditError):
        dg.undo(db, plant.id, user)
    dg.add_edit(db, plant.id, user, {"op": "rename_node", "id": "eq:V-102", "label": "V-102A"})    # yangi tahrir redo ni yopadi
    assert not dg.get(db, plant.id)["can_redo"] and db.query(DiagramEdit).count() == 1
    actions = [a.action for a in db.query(AuditLog)]
    assert {"diagram.generate", "diagram.edit", "diagram.undo", "diagram.redo"} <= set(actions)


def test_edit_that_does_not_apply_is_refused(db, plant, user):
    dg.regenerate(db, plant.id, user)
    with pytest.raises(EditError):
        dg.add_edit(db, plant.id, user, {"op": "move", "id": "eq:YOQ", "x": 1, "y": 1})
    with pytest.raises(EditError):
        dg.add_edit(db, plant.id, user, {"op": "add_edge", "id": "m:1", "from": "eq:V-101", "to": "eq:V-101", "label": ""})
    assert db.query(DiagramEdit).count() == 0
    with pytest.raises(EditError):
        dg.add_edit(db, 99999, user, {"op": "move", "id": "eq:V-101", "x": 1, "y": 1})


def test_edits_survive_regeneration_and_orphans_are_reported(db, plant, user):
    dg.regenerate(db, plant.id, user)
    dg.add_edit(db, plant.id, user, {"op": "move", "id": "eq:V-102", "x": 900, "y": 90})
    dg.add_edit(db, plant.id, user, {"op": "rename_node", "id": "eq:E-101", "label": "E-101X"})
    eql = make_doc(db, plant, EQL, "GP-EQL-001", "B")           # yangi reviziya: E-101 yo'q, V-103 qo'shilgan
    for tag in ("V-101", "V-102", "P-101A", "V-103"):
        make_param(db, plant, eql, tag, "material", "CS")
    assert dg.get(db, plant.id)["stale"] is True
    dg.regenerate(db, plant.id, user)
    d = dg.get(db, plant.id)
    assert d["stale"] is False and "eq:V-103" in _ids(d["nodes"]) and "eq:E-101" not in _ids(d["nodes"])
    assert next(n for n in d["nodes"] if n["id"] == "eq:V-102")["x"] == 900          # tahrir saqlandi
    assert [o["op"]["op"] for o in d["orphan_edits"]] == ["rename_node"]             # qo'llanmagan tahrir ko'rsatiladi


def test_differences_from_documents(db, plant, user):
    dg.regenerate(db, plant.id, user)
    assert dg.get(db, plant.id)["differences"] == []
    dg.add_edit(db, plant.id, user, {"op": "move", "id": "eq:V-102", "x": 1, "y": 1})          # ko'chirish farq emas
    dg.add_edit(db, plant.id, user, {"op": "add_node", "id": "m:1", "label": "V-103", "kind": "vessel", "x": 1, "y": 2})
    dg.add_edit(db, plant.id, user, {"op": "remove_node", "id": "eq:E-101"})
    dg.add_edit(db, plant.id, user, {"op": "rename_node", "id": "eq:V-102", "label": "V-102A"})
    dg.add_edit(db, plant.id, user, {"op": "add_edge", "id": "m:2", "from": "eq:V-102", "to": "m:1", "label": "L"})
    dg.add_edit(db, plant.id, user, {"op": "remove_edge", "id": 'ln:6"-AM-1003-B1A'})
    kinds = sorted((x["kind"], x["label"]) for x in dg.get(db, plant.id)["differences"])
    assert kinds == [("edge_added", "L"), ("edge_removed", '6"-AM-1003-B1A'), ("node_added", "V-103"),
                     ("node_removed", "E-101"), ("node_renamed", "V-102 → V-102A")]


def test_svg_export_escapes_labels_and_marks_sources(db, plant, user):
    dg.regenerate(db, plant.id, user)
    dg.add_edit(db, plant.id, user, {"op": "add_node", "id": "m:1", "label": "<script>alert(1)</script>", "kind": "vessel", "x": 1, "y": 2})
    svg = render_svg(dg.get(db, plant.id))
    assert svg.startswith("<svg") and "<script>" not in svg and "&lt;script&gt;" in svg
    assert "V-101" in svg and 'data-source="manual"' in svg and svg.count("<line") + svg.count("<path") >= 3
