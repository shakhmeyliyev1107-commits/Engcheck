"""Prinsipial sxema: yaratish, o'qish, tahrirlash, orqaga/oldinga, SVG eksport."""
from fastapi import APIRouter, Body, Depends, Response
from sqlalchemy.orm import Session as Db

from ..core.auth import Perm
from ..core.models import User
from ..diagram import service as diagram
from ..diagram.svg import render_svg
from .deps import get_db, require
from .errors import ApiError
from .routes_projects import get_project

router = APIRouter()
_STATUS = {"invalid_op": 422, "not_applicable": 409, "nothing_to_undo": 409, "nothing_to_redo": 409, "no_diagram": 409}


def _guard(fn):
    try:
        return fn()
    except diagram.EditError as exc:
        raise ApiError(_STATUS.get(exc.code, 422), f"diagram_{exc.code}") from exc


@router.get("/projects/{project_id}/diagram")
def read_diagram(project_id: int, _: User = Depends(require(Perm.view)), db: Db = Depends(get_db)):
    get_project(db, project_id)
    return diagram.get(db, project_id)


@router.post("/projects/{project_id}/diagram/generate")
def generate_diagram(project_id: int, user: User = Depends(require(Perm.review)), db: Db = Depends(get_db)):
    get_project(db, project_id)
    return _guard(lambda: diagram.regenerate(db, project_id, user))


@router.post("/projects/{project_id}/diagram/edits", status_code=201)
def edit_diagram(project_id: int, op: dict = Body(...), user: User = Depends(require(Perm.decide)),
                 db: Db = Depends(get_db)):
    get_project(db, project_id)
    return _guard(lambda: diagram.add_edit(db, project_id, user, op))


@router.post("/projects/{project_id}/diagram/undo")
def undo_edit(project_id: int, user: User = Depends(require(Perm.decide)), db: Db = Depends(get_db)):
    get_project(db, project_id)
    return _guard(lambda: diagram.undo(db, project_id, user))


@router.post("/projects/{project_id}/diagram/redo")
def redo_edit(project_id: int, user: User = Depends(require(Perm.decide)), db: Db = Depends(get_db)):
    get_project(db, project_id)
    return _guard(lambda: diagram.redo(db, project_id, user))


@router.get("/projects/{project_id}/diagram.svg")
def export_svg(project_id: int, _: User = Depends(require(Perm.view)), db: Db = Depends(get_db)):
    get_project(db, project_id)
    return Response(content=render_svg(diagram.get(db, project_id)), media_type="image/svg+xml",
                    headers={"Content-Disposition": f'attachment; filename="diagram-{project_id}.svg"',
                             "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})
