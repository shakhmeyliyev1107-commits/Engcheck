import pytest

from engcheck.core.auth import create_user
from engcheck.core.models import AuditLog, Discipline, LayoutEdit, Method, TagOccurrence
from engcheck.layout3d import service as l3
from engcheck.layout3d.edits import EditError, apply_edits, validate_op
from engcheck.layout3d.generator import DEFAULT_SIZE, generate

from ..review.factories import DS, EQL, PID, make_doc, make_param, make_tag


@pytest.fixture
def user(db):
    return create_user(db, "aziz", "S3cret-pass", "engineer")


def _plot(db, project, placements, number="GP-PLT-001", rev="A"):
    """Bosh reja: intizomi civil bo'lgan DXF hujjat, uskuna bloklari koordinatasi bilan."""
    from engcheck.core.models import DocType
    doc = make_doc(db, project, DocType.OTHER, number, rev)
    doc.discipline = Discipline.civil
    for tag, (x, y) in placements.items():
        make_tag(db, project, doc, tag)
        occ = db.query(TagOccurrence).filter_by(document_id=doc.id).order_by(TagOccurrence.id.desc()).first()
        occ.location = f"x={float(x)},y={float(y)}"
    db.flush()
    return doc


@pytest.fixture
def plant(db, project):
    eql, ds = make_doc(db, project, EQL, "GP-EQL-001"), make_doc(db, project, DS, "GP-DS-V101")
    for tag in ("V-101", "P-101A", "E-101", "T-201"):
        make_param(db, project, eql, tag, "material", "CS")
    make_param(db, project, ds, "V-101", "size", "2400 mm", 2400.0)
    make_param(db, project, ds, "V-101", "equipment_height", "9 m", 9000.0)
    make_param(db, project, ds, "V-101", "material", "CS"); make_param(db, project, ds, "V-101", "design_pressure", "16 barg", 1600.0)
    make_param(db, project, ds, "V-101", "design_temperature", "120 C", 120.0)
    return project


def _by(model):
    return {i["id"]: i for i in model["items"]}


def test_positions_from_civil_plot_plan_in_metres(db, plant):
    _plot(db, plant, {"V-101": (10, 20), "P-101A": (30, 20), "E-101": (10, 60)})
    m = generate(db, plant.id)
    items = _by(m)
    assert (items["eq:V-101"]["x"], items["eq:V-101"]["y"], items["eq:V-101"]["position_source"]) == (10.0, 20.0, "document")
    assert (items["eq:P-101A"]["x"], items["eq:E-101"]["y"]) == (30.0, 60.0)        # chizmaning o'z koordinatalari, metrda
    assert items["eq:T-201"]["position_source"] == "assumed"                       # bosh rejada yo'q
    assert m["unit_assumed"] == "m" and m["plot_plan"] == "GP-PLT-001"


def test_large_drawing_extent_is_taken_as_millimetres_and_flagged(db, plant):
    _plot(db, plant, {"V-101": (10000, 20000), "P-101A": (30000, 20000)})
    m = generate(db, plant.id)
    assert m["unit_assumed"] == "mm" and _by(m)["eq:P-101A"]["x"] == 30.0


def test_without_plot_plan_everything_is_on_an_assumed_grid(db, plant):
    m = generate(db, plant.id)
    assert m["plot_plan"] is None and m["unit_assumed"] is None
    assert {i["position_source"] for i in m["items"]} == {"assumed"}
    assert len({(i["x"], i["y"]) for i in m["items"]}) == 4                        # ustma-ust tushmaydi
    assert generate(db, plant.id) == m                                             # barqaror


def test_pid_coordinates_are_not_physical_positions(db, plant):
    pid = make_doc(db, plant, PID)
    make_tag(db, plant, pid, "V-101")
    db.query(TagOccurrence).filter_by(document_id=pid.id).one().location = "x=500.0,y=500.0"
    db.flush()
    assert _by(generate(db, plant.id))["eq:V-101"]["position_source"] == "assumed"


def test_sizes_from_documents_else_nominal_by_kind(db, plant):
    items = _by(generate(db, plant.id))
    v = items["eq:V-101"]
    assert (v["shape"], v["w"], v["d"], v["h"], v["size_source"]) == ("cylinder_v", 2.4, 2.4, 9.0, "document")
    p = items["eq:P-101A"]
    assert p["size_source"] == "assumed" and (p["w"], p["d"], p["h"]) == DEFAULT_SIZE["pump"] and p["shape"] == "box"
    assert items["eq:E-101"]["shape"] == "cylinder_h" and items["eq:T-201"]["kind"] == "column"
    assert all(i["z"] == 0 and i["rot"] == 0 for i in items.values())


def test_partial_document_size_keeps_known_dimension_only(db, project):
    ds = make_doc(db, project, DS)
    make_param(db, project, ds, "V-300", "size", "3 m", 3000.0)
    make_param(db, project, ds, "V-300", "material", "CS")
    v = _by(generate(db, project.id))["eq:V-300"]
    assert (v["w"], v["h"], v["size_source"]) == (3.0, DEFAULT_SIZE["vessel"][2], "partial")


def test_absurd_document_size_is_not_used(db, project):
    ds = make_doc(db, project, DS)
    make_param(db, project, ds, "V-300", "size", "0 mm", 0.0); make_param(db, project, ds, "V-300", "equipment_height", "900 km", 9e8)
    make_param(db, project, ds, "V-300", "material", "CS")
    v = _by(generate(db, project.id))["eq:V-300"]
    assert v["size_source"] == "assumed" and (v["w"], v["d"], v["h"]) == DEFAULT_SIZE["vessel"]


def test_superseded_plot_plan_revision_is_ignored(db, plant):
    _plot(db, plant, {"V-101": (0, 0), "P-101A": (99, 0)}, rev="A")
    _plot(db, plant, {"V-101": (0, 0), "P-101A": (15, 0)}, rev="B")
    assert _by(generate(db, plant.id))["eq:P-101A"]["x"] == 15.0


def test_free_text_mentions_do_not_become_equipment(db, project):
    eql = make_doc(db, project, EQL)
    make_param(db, project, eql, "V-101", "material", "CS")
    make_tag(db, project, eql, "V-777", method=Method.regex)
    assert list(_by(generate(db, project.id))) == ["eq:V-101"]


# ---------- tahrirlar ----------
def test_edits_apply_and_mark_manual(db, plant):
    g = generate(db, plant.id)
    d, skipped = apply_edits(g, [
        {"op": "move", "id": "eq:V-101", "x": 12.5, "y": -3},
        {"op": "rotate", "id": "eq:E-101", "rot": 90},
        {"op": "resize", "id": "eq:P-101A", "w": 2, "d": 1, "h": 1.2},
        {"op": "rename", "id": "eq:T-201", "label": "T-201A"},
        {"op": "add_item", "id": "m:1", "label": "TK-900", "kind": "tank", "x": 50, "y": 50},
        {"op": "remove_item", "id": "eq:T-201"}, {"op": "move", "id": "eq:YOQ", "x": 1, "y": 1},
    ])
    items = _by(d)
    assert skipped == [6] and "eq:T-201" not in items
    assert (items["eq:V-101"]["x"], items["eq:V-101"]["y"], items["eq:V-101"]["position_source"]) == (12.5, -3.0, "manual")
    assert items["eq:E-101"]["rot"] == 90 and items["eq:P-101A"]["size_source"] == "manual" and items["eq:P-101A"]["h"] == 1.2
    tank = items["m:1"]
    assert (tank["source"], tank["shape"], tank["size_source"], tank["position_source"]) == ("manual", "cylinder_v", "assumed", "manual")
    assert _by(g)["eq:V-101"]["position_source"] != "manual"       # yaratilgan qatlam o'zgarmadi


@pytest.mark.parametrize("op", [
    {"op": "fly"}, {"op": "move", "id": "eq:V-101", "x": "a", "y": 1}, {"op": "move", "id": "eq:V-101", "x": float("inf"), "y": 1},
    {"op": "move", "id": "eq:V-101", "x": 10 ** 400, "y": 1}, {"op": "move", "id": "eq:V-101", "x": 1e7, "y": 1},
    {"op": "rotate", "id": "eq:V-101", "rot": 720}, {"op": "rotate", "id": "eq:V-101", "rot": True},
    {"op": "resize", "id": "eq:V-101", "w": 0, "d": 1, "h": 1}, {"op": "resize", "id": "eq:V-101", "w": 1, "d": 1, "h": 5000},
    {"op": "resize", "id": "eq:V-101", "w": -1, "d": 1, "h": 1},
    {"op": "add_item", "id": "eq:FAKE", "label": "x", "kind": "tank", "x": 1, "y": 1},
    {"op": "add_item", "id": "m:1", "label": "x", "kind": "boundary", "x": 1, "y": 1},
    {"op": "add_item", "id": "m:1", "label": "a‮b", "kind": "tank", "x": 1, "y": 1},
    {"op": "rename", "id": "eq:V-101", "label": ""}, {"op": "remove_item"}, [], None,
])
def test_invalid_ops(op):
    with pytest.raises(EditError):
        validate_op(op)


def test_service_generate_edit_undo_redo_and_audit(db, plant, user):
    assert l3.get(db, plant.id)["exists"] is False
    with pytest.raises(EditError):
        l3.add_edit(db, plant.id, user, {"op": "move", "id": "eq:V-101", "x": 1, "y": 1})
    l3.regenerate(db, plant.id, user)
    l3.add_edit(db, plant.id, user, {"op": "move", "id": "eq:V-101", "x": 40, "y": 5})
    l3.add_edit(db, plant.id, user, {"op": "rotate", "id": "eq:E-101", "rot": 45})
    with pytest.raises(EditError):
        l3.add_edit(db, plant.id, user, {"op": "move", "id": "eq:YOQ", "x": 1, "y": 1})
    assert _by(l3.undo(db, plant.id, user))["eq:E-101"]["rot"] == 0
    m = l3.get(db, plant.id)
    assert m["can_undo"] and m["can_redo"] and _by(m)["eq:V-101"]["x"] == 40
    assert _by(l3.redo(db, plant.id, user))["eq:E-101"]["rot"] == 45
    l3.undo(db, plant.id, user)
    l3.add_edit(db, plant.id, user, {"op": "rename", "id": "eq:P-101A", "label": "P-101X"})    # redo yopiladi
    assert not l3.get(db, plant.id)["can_redo"] and db.query(LayoutEdit).count() == 2
    assert {"layout3d.generate", "layout3d.edit", "layout3d.undo", "layout3d.redo"} <= {a.action for a in db.query(AuditLog)}


def test_edits_survive_regeneration_and_orphans_reported(db, plant, user):
    l3.regenerate(db, plant.id, user)
    l3.add_edit(db, plant.id, user, {"op": "move", "id": "eq:P-101A", "x": 77, "y": 7})
    l3.add_edit(db, plant.id, user, {"op": "rotate", "id": "eq:T-201", "rot": 30})
    eql = make_doc(db, plant, EQL, "GP-EQL-001", "B")                          # yangi reviziya: T-201 yo'q
    for tag in ("V-101", "P-101A", "E-101"):
        make_param(db, plant, eql, tag, "material", "CS")
    assert l3.get(db, plant.id)["stale"] is True
    m = l3.regenerate(db, plant.id, user)
    assert m["stale"] is False and "eq:T-201" not in _by(m) and _by(m)["eq:P-101A"]["x"] == 77
    assert [o["op"]["op"] for o in m["orphan_edits"]] == ["rotate"]


def test_differences_only_count_changes_to_document_values(db, plant, user):
    _plot(db, plant, {"V-101": (10, 20), "P-101A": (30, 20)})
    l3.regenerate(db, plant.id, user)
    assert l3.get(db, plant.id)["differences"] == []
    l3.add_edit(db, plant.id, user, {"op": "move", "id": "eq:E-101", "x": 5, "y": 5})          # taxminiy joy edi — farq emas
    l3.add_edit(db, plant.id, user, {"op": "resize", "id": "eq:P-101A", "w": 2, "d": 1, "h": 1})  # shartli o'lcham edi — farq emas
    assert l3.get(db, plant.id)["differences"] == []
    l3.add_edit(db, plant.id, user, {"op": "move", "id": "eq:V-101", "x": 3, "y": 0})          # bosh rejadagi joy o'zgardi
    l3.add_edit(db, plant.id, user, {"op": "resize", "id": "eq:V-101", "w": 3, "d": 3, "h": 9})  # datasheetdagi o'lcham o'zgardi
    l3.add_edit(db, plant.id, user, {"op": "rename", "id": "eq:E-101", "label": "E-101X"})
    l3.add_edit(db, plant.id, user, {"op": "add_item", "id": "m:1", "label": "TK-900", "kind": "tank", "x": 1, "y": 2})
    l3.add_edit(db, plant.id, user, {"op": "remove_item", "id": "eq:T-201"})
    kinds = sorted((x["kind"], x["label"]) for x in l3.get(db, plant.id)["differences"])
    assert kinds == [("item_added", "TK-900"), ("item_removed", "T-201"), ("item_renamed", "E-101 → E-101X"),
                     ("position_changed", "V-101"), ("size_changed", "V-101")]


# --- mustaqil ko'rikdan keyingi tuzatishlar ---

def test_manual_position_stays_put_relative_to_documents_when_plot_plan_grows(db, plant, user):
    _plot(db, plant, {"V-101": (10, 10), "P-101A": (20, 10)}, rev="A")
    l3.regenerate(db, plant.id, user)
    l3.add_edit(db, plant.id, user, {"op": "move", "id": "eq:P-101A", "x": 21, "y": 10})   # V-101 dan 11 m sharqda
    _plot(db, plant, {"V-101": (10, 10), "P-101A": (20, 10), "E-101": (0, 0)}, rev="B")     # chizma chegarasi kengaydi
    items = _by(l3.regenerate(db, plant.id, user))
    assert (items["eq:V-101"]["x"], items["eq:V-101"]["y"]) == (10.0, 10.0)                # hujjatdagi joy siljimaydi
    assert items["eq:P-101A"]["x"] - items["eq:V-101"]["x"] == 11.0


def test_conflicting_document_sizes_are_flagged_and_datasheet_wins(db, project):
    eql, ds = make_doc(db, project, EQL, "EQL-1"), make_doc(db, project, DS, "DS-1")
    make_param(db, project, eql, "V-300", "size", "1200 mm", 1200.0); make_param(db, project, eql, "V-300", "equipment_height", "4 m", 4000.0)
    make_param(db, project, ds, "V-300", "size", "2400 mm", 2400.0); make_param(db, project, ds, "V-300", "equipment_height", "9 m", 9000.0)
    v = _by(generate(db, project.id))["eq:V-300"]
    assert (v["w"], v["h"], v["size_source"]) == (2.4, 9.0, "conflict")


def test_agreeing_document_sizes_are_not_a_conflict(db, project):
    eql, ds = make_doc(db, project, EQL, "EQL-1"), make_doc(db, project, DS, "DS-1")
    for d in (eql, ds):
        make_param(db, project, d, "V-300", "size", "2400 mm", 2400.0); make_param(db, project, d, "V-300", "equipment_height", "9 m", 9000.0)
    assert _by(generate(db, project.id))["eq:V-300"]["size_source"] == "document"


def test_nominal_size_is_not_a_shell_diameter(db, project):
    ds = make_doc(db, project, DS)
    make_param(db, project, ds, "V-300", "size", "DN 80", 80.0); make_param(db, project, ds, "V-300", "equipment_height", "6 m", 6000.0)
    v = _by(generate(db, project.id))["eq:V-300"]
    assert (v["w"], v["h"], v["size_source"]) == (DEFAULT_SIZE["vessel"][0], 6.0, "partial")


def test_length_used_as_height_is_an_interpretation_not_a_document_fact(db, project):
    ds = make_doc(db, project, DS)
    make_param(db, project, ds, "V-300", "size", "2 m", 2000.0); make_param(db, project, ds, "V-300", "equipment_length", "6 m", 6000.0)
    v = _by(generate(db, project.id))["eq:V-300"]
    assert (v["h"], v["size_source"]) == (6.0, "partial")


def test_sizes_are_not_taken_from_pid_or_other_documents(db, project):
    pid, ds = make_doc(db, project, PID, "PID-1"), make_doc(db, project, DS, "DS-1")
    make_param(db, project, pid, "V-300", "size", "150 mm", 150.0)
    make_param(db, project, ds, "V-300", "material", "CS")
    assert _by(generate(db, project.id))["eq:V-300"]["size_source"] == "assumed"


def test_noop_move_and_resize_keep_document_source_labels(db, plant, user):
    _plot(db, plant, {"V-101": (10, 20)})
    l3.regenerate(db, plant.id, user)
    m = l3.add_edit(db, plant.id, user, {"op": "move", "id": "eq:V-101", "x": 10, "y": 20})
    m = l3.add_edit(db, plant.id, user, {"op": "resize", "id": "eq:V-101", "w": 2.4, "d": 2.4, "h": 9})
    v = _by(m)["eq:V-101"]
    assert (v["position_source"], v["size_source"]) == ("document", "document") and m["differences"] == []
