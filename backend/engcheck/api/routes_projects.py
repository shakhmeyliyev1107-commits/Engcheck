from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as Db

from ..core import audit
from ..core.auth import Perm
from ..core.models import Document, Project, ReviewRun, Stage, User
from ..ingest.service import delete_document
from .deps import get_db, require
from .errors import ApiError
from .serializers import project_out

router = APIRouter()
Industry = Literal["gtl", "mto", "oil_refining", "gas_processing", "water_treatment",
                   "wastewater_treatment"]


class NewProject(BaseModel):
    name: str = Field(min_length=1, max_length=200, pattern=r"\S")
    industry: Industry
    stage: Stage


def get_project(db: Db, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise ApiError(404, "not_found")
    return project


@router.get("/projects")
def list_projects(_: User = Depends(require(Perm.view)), db: Db = Depends(get_db)):
    return [project_out(p) for p in db.query(Project).order_by(Project.id.desc())]


@router.post("/projects", status_code=201)
def create_project(body: NewProject, user: User = Depends(require(Perm.upload)),
                   db: Db = Depends(get_db)):
    project = Project(name=body.name.strip(), industry=body.industry, stage=body.stage,
                      created_by=user.id)
    db.add(project)
    db.flush()
    audit.record(db, user.id, "project.create", "project", project.id, {"name": project.name})
    return project_out(project)


@router.get("/projects/{project_id}")
def read_project(project_id: int, _: User = Depends(require(Perm.view)), db: Db = Depends(get_db)):
    return project_out(get_project(db, project_id))


class ProjectPatch(BaseModel):
    allow_cloud_ai: bool


@router.patch("/projects/{project_id}")
def update_project(project_id: int, body: ProjectPatch, user: User = Depends(require(Perm.manage_kb)),
                   db: Db = Depends(get_db)):
    """Loyiha matnlarini bulutli AI ga yuborishga ruxsat (yetakchi muhandis yoki administrator)."""
    project = get_project(db, project_id)
    project.allow_cloud_ai = body.allow_cloud_ai
    audit.record(db, user.id, "project.update", "project", project.id, {"allow_cloud_ai": body.allow_cloud_ai})
    return project_out(project)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: int, request: Request,
                   user: User = Depends(require(Perm.delete_project)), db: Db = Depends(get_db)):
    project = get_project(db, project_id)
    name = project.name
    settings = request.app.state.settings
    db.query(ReviewRun).filter_by(project_id=project_id).delete()
    for doc in db.query(Document).filter_by(project_id=project_id).all():
        delete_document(db, settings, doc.id, user.id)
    db.query(Project).filter_by(id=project_id).delete()
    db.flush()
    db.expire_all()
    audit.record(db, user.id, "project.delete", "project", project_id, {"name": name})
    return Response(status_code=204)
