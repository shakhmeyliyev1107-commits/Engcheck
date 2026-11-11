"""3D joylashuv modeli: yaratish, o'qish, tahrirlash, orqaga/oldinga."""
from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session as Db

from ..core.auth import Perm
from ..core.models import User
from ..layout3d import service as layout3d
from .deps import get_db, require
from .errors import ApiError
from .routes_projects import get_project

router = APIRouter()
_STATUS = {"invalid_op": 422, "not_applicable": 409, "nothing_to_undo": 409, "nothing_to_redo": 409, "no_layout": 409}


def _guard(fn):
    try:
        return fn()
    except layout3d.EditError as exc:
        raise ApiError(_STATUS.get(exc.code, 422), f"layout3d_{exc.code}") from exc


@router.get("/projects/{project_id}/layout3d")
def read_layout(project_id: int, _: User = Depends(require(Perm.view)), db: Db = Depends(get_db)):
    get_project(db, project_id)
    return layout3d.get(db, project_id)


@router.post("/projects/{project_id}/layout3d/generate")
def generate_layout(project_id: int, user: User = Depends(require(Perm.review)), db: Db = Depends(get_db)):
    get_project(db, project_id)
    return _guard(lambda: layout3d.regenerate(db, project_id, user))


@router.post("/projects/{project_id}/layout3d/edits", status_code=201)
def edit_layout(project_id: int, op: dict = Body(...), user: User = Depends(require(Perm.decide)),
                db: Db = Depends(get_db)):
    get_project(db, project_id)
    return _guard(lambda: layout3d.add_edit(db, project_id, user, op))


@router.post("/projects/{project_id}/layout3d/undo")
def undo_edit(project_id: int, user: User = Depends(require(Perm.decide)), db: Db = Depends(get_db)):
    get_project(db, project_id)
    return _guard(lambda: layout3d.undo(db, project_id, user))


@router.post("/projects/{project_id}/layout3d/redo")
def redo_edit(project_id: int, user: User = Depends(require(Perm.decide)), db: Db = Depends(get_db)):
    get_project(db, project_id)
    return _guard(lambda: layout3d.redo(db, project_id, user))
