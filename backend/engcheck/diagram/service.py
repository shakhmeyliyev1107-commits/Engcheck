"""Sxema xizmati: yaratish, o'qish, tahrirlash, orqaga/oldinga."""
from sqlalchemy.orm import Session as Db

from ..core import audit
from ..core.models import Diagram, DiagramEdit, Project, User, utcnow
from .edits import EditError, apply_edits, apply_one, differences, validate_op
from .generator import generate, source_hash

__all__ = ["EditError", "get", "regenerate", "add_edit", "undo", "redo"]


def _row(db: Db, project_id: int) -> Diagram | None:
    return db.query(Diagram).filter_by(project_id=project_id).first()


def _edits(db: Db, project_id: int) -> list[DiagramEdit]:
    return db.query(DiagramEdit).filter_by(project_id=project_id).order_by(DiagramEdit.id).all()


def get(db: Db, project_id: int) -> dict:
    row = _row(db, project_id)
    if row is None:
        return {"exists": False, "nodes": [], "edges": [], "unconnected": [], "differences": [], "orphan_edits": [],
                "can_undo": False, "can_redo": False, "stale": False, "generated_at": None}
    edits = _edits(db, project_id)
    active = [e for e in edits if not e.undone]
    effective, skipped = apply_edits(row.generated, [e.op for e in active])
    return {"exists": True, "nodes": effective["nodes"], "edges": effective["edges"],
            "unconnected": effective.get("unconnected", []),
            "differences": differences(row.generated, effective),
            "orphan_edits": [{"id": active[i].id, "op": active[i].op} for i in skipped],
            "can_undo": bool(active), "can_redo": any(e.undone for e in edits),
            "stale": row.source_hash != source_hash(db, project_id),
            "generated_at": row.generated_at.isoformat()}


def regenerate(db: Db, project_id: int, user: User | None) -> dict:
    """Yaratilgan qatlamni hujjatlardan qayta quradi. Tahrirlar qatlamiga tegmaydi."""
    if db.get(Project, project_id) is None:
        raise EditError("no_diagram")
    row = _row(db, project_id)
    generated = generate(db, project_id)
    if row is None:
        row = Diagram(project_id=project_id, generated=generated, source_hash="")
        db.add(row)
    row.generated, row.source_hash = generated, source_hash(db, project_id)
    row.generated_at, row.generated_by = utcnow(), user.id if user else None
    db.flush()
    audit.record(db, user.id if user else None, "diagram.generate", "project", project_id,
                 {"nodes": len(generated["nodes"]), "edges": len(generated["edges"])})
    return get(db, project_id)


def add_edit(db: Db, project_id: int, user: User | None, op) -> dict:
    row = _row(db, project_id)
    if row is None:
        raise EditError("no_diagram")
    op = validate_op(op)
    edits = _edits(db, project_id)
    effective, _ = apply_edits(row.generated, [e.op for e in edits if not e.undone])
    if not apply_one(effective, op):
        raise EditError("not_applicable")   # mavjud bo'lmagan tugun, takror id, o'ziga ulanish va h.k.
    for e in edits:
        if e.undone:
            db.delete(e)   # yangi tahrir "oldinga" tarixini yopadi
    db.add(DiagramEdit(project_id=project_id, op=op, user_id=user.id if user else None))
    db.flush()
    audit.record(db, user.id if user else None, "diagram.edit", "project", project_id, op)
    return get(db, project_id)


def undo(db: Db, project_id: int, user: User | None) -> dict:
    active = [e for e in _edits(db, project_id) if not e.undone]
    if not active:
        raise EditError("nothing_to_undo")
    active[-1].undone = True
    db.flush()
    audit.record(db, user.id if user else None, "diagram.undo", "project", project_id, active[-1].op)
    return get(db, project_id)


def redo(db: Db, project_id: int, user: User | None) -> dict:
    undone = [e for e in _edits(db, project_id) if e.undone]
    if not undone:
        raise EditError("nothing_to_redo")
    undone[0].undone = False
    db.flush()
    audit.record(db, user.id if user else None, "diagram.redo", "project", project_id, undone[0].op)
    return get(db, project_id)
