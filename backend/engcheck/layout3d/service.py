"""3D model xizmati: yaratish, o'qish, tahrirlash, orqaga/oldinga (sxema xizmati bilan bir xil tartib)."""
from sqlalchemy.orm import Session as Db

from ..core import audit
from ..core.models import Layout3d, LayoutEdit, Project, User, utcnow
from ..diagram.generator import source_hash
from .edits import EditError, apply_edits, apply_one, differences, validate_op
from .generator import generate

__all__ = ["EditError", "get", "regenerate", "add_edit", "undo", "redo"]


def _row(db: Db, project_id: int) -> Layout3d | None:
    return db.query(Layout3d).filter_by(project_id=project_id).first()


def _edits(db: Db, project_id: int) -> list[LayoutEdit]:
    return db.query(LayoutEdit).filter_by(project_id=project_id).order_by(LayoutEdit.id).all()


def get(db: Db, project_id: int) -> dict:
    row = _row(db, project_id)
    if row is None:
        return {"exists": False, "items": [], "unit_assumed": None, "plot_plan": None, "differences": [],
                "orphan_edits": [], "can_undo": False, "can_redo": False, "stale": False, "generated_at": None}
    edits = _edits(db, project_id)
    active = [e for e in edits if not e.undone]
    effective, skipped = apply_edits(row.generated, [e.op for e in active])
    return {"exists": True, "items": effective["items"], "unit_assumed": effective.get("unit_assumed"),
            "plot_plan": effective.get("plot_plan"), "differences": differences(row.generated, effective),
            "orphan_edits": [{"id": active[i].id, "op": active[i].op} for i in skipped],
            "can_undo": bool(active), "can_redo": any(e.undone for e in edits),
            "stale": row.source_hash != source_hash(db, project_id), "generated_at": row.generated_at.isoformat()}


def regenerate(db: Db, project_id: int, user: User | None) -> dict:
    if db.get(Project, project_id) is None:
        raise EditError("no_layout")
    row = _row(db, project_id)
    generated = generate(db, project_id)
    if row is None:
        row = Layout3d(project_id=project_id, generated=generated, source_hash="")
        db.add(row)
    row.generated, row.source_hash = generated, source_hash(db, project_id)
    row.generated_at, row.generated_by = utcnow(), user.id if user else None
    db.flush()
    audit.record(db, user.id if user else None, "layout3d.generate", "project", project_id,
                 {"items": len(generated["items"]), "plot_plan": generated["plot_plan"]})
    return get(db, project_id)


def add_edit(db: Db, project_id: int, user: User | None, op) -> dict:
    row = _row(db, project_id)
    if row is None:
        raise EditError("no_layout")
    op = validate_op(op)
    edits = _edits(db, project_id)
    effective, _ = apply_edits(row.generated, [e.op for e in edits if not e.undone])
    if not apply_one(effective, op):
        raise EditError("not_applicable")
    for e in edits:
        if e.undone:
            db.delete(e)
    db.add(LayoutEdit(project_id=project_id, op=op, user_id=user.id if user else None))
    db.flush()
    audit.record(db, user.id if user else None, "layout3d.edit", "project", project_id, op)
    return get(db, project_id)


def undo(db: Db, project_id: int, user: User | None) -> dict:
    active = [e for e in _edits(db, project_id) if not e.undone]
    if not active:
        raise EditError("nothing_to_undo")
    active[-1].undone = True
    db.flush()
    audit.record(db, user.id if user else None, "layout3d.undo", "project", project_id, active[-1].op)
    return get(db, project_id)


def redo(db: Db, project_id: int, user: User | None) -> dict:
    undone = [e for e in _edits(db, project_id) if e.undone]
    if not undone:
        raise EditError("nothing_to_redo")
    undone[0].undone = False
    db.flush()
    audit.record(db, user.id if user else None, "layout3d.redo", "project", project_id, undone[0].op)
    return get(db, project_id)
