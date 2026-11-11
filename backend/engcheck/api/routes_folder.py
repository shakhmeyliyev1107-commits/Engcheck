"""Loyihaga hujjatlar papkasini ulash, skanerlash va undagi fayllarni yuklash."""
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as Db

from ..core import audit
from ..core.auth import Perm
from ..core.models import Discipline, DocType, Document, User
from ..ingest import folder, service
from .deps import get_db, require
from .errors import ApiError
from .routes_projects import get_project

router = APIRouter()


class FolderLink(BaseModel):
    path: str | None = Field(None, max_length=1000)


class FolderFile(BaseModel):
    path: str = Field(max_length=1000)
    doc_type: DocType
    discipline: Discipline
    doc_number: str | None = Field(None, max_length=80)
    revision: str | None = Field(None, max_length=20)


class FolderImport(BaseModel):
    files: list[FolderFile] = Field(max_length=500)


def _root(project) -> Path:
    if not project.source_folder:
        raise ApiError(409, "folder_not_linked")
    try:
        return folder.resolve(project.source_folder)
    except folder.FolderError as exc:
        raise ApiError(409, exc.code) from exc


@router.get("/projects/{project_id}/folder")
def get_folder(project_id: int, _: User = Depends(require(Perm.view)), db: Db = Depends(get_db)):
    return {"path": get_project(db, project_id).source_folder}


@router.put("/projects/{project_id}/folder")
def link_folder(project_id: int, body: FolderLink, user: User = Depends(require(Perm.link_folder)),
                db: Db = Depends(get_db)):
    """Papkani ulash — server diskidagi ixtiyoriy katalogni o'qishga ruxsat berish demak, shuning uchun faqat rahbar/administrator."""
    project = get_project(db, project_id)
    if body.path is None or not body.path.strip():
        project.source_folder = None
    else:
        try:
            project.source_folder = str(folder.resolve(body.path))
        except folder.FolderError as exc:
            raise ApiError(422, exc.code) from exc
    audit.record(db, user.id, "project.folder_link", "project", project.id, {"path": project.source_folder})
    db.commit()
    return {"path": project.source_folder}


@router.get("/projects/{project_id}/folder/scan")
def scan_folder(project_id: int, _: User = Depends(require(Perm.upload)), db: Db = Depends(get_db)):
    project = get_project(db, project_id)
    root = _root(project)
    try:
        found, truncated = folder.scan(root)
    except folder.FolderError as exc:
        raise ApiError(409, exc.code) from exc
    known = {sha for (sha,) in db.query(Document.sha256).filter_by(project_id=project_id)}
    files = []
    for item in found:
        name = Path(item["path"]).name
        if not item["supported"]:
            status = "unsupported"
        elif item["size"] > folder.MAX_SIZE:
            status = "too_large"
        else:
            try:
                status = "imported" if service._sha256(root / item["path"]) in known else "new"
            except OSError:
                status = "unreadable"
        doc_type = service.suggest_doc_type(name)
        number, revision = service.suggest_number_revision(name)
        files.append({"path": item["path"], "size": item["size"], "status": status,
                      "doc_type": doc_type.value if doc_type else None, "doc_number": number, "revision": revision})
    return {"path": project.source_folder, "files": files, "truncated": truncated}


@router.post("/projects/{project_id}/folder/import")
def import_folder(project_id: int, body: FolderImport, request: Request,
                  user: User = Depends(require(Perm.upload)), db: Db = Depends(get_db)):
    project = get_project(db, project_id)
    root = _root(project)
    results = []
    for item in body.files:
        src = folder.locate(root, item.path)
        if src is None:
            results.append({"path": item.path, "status": "error", "code": "folder_file_unavailable"})
            continue
        try:
            if src.stat().st_size > folder.MAX_SIZE:
                results.append({"path": item.path, "status": "error", "code": "folder_file_too_large"})
                continue
            number, revision = service.suggest_number_revision(src.name)   # kiritilmagan bo'lsa — fayl nomidan
            doc = service.ingest_file(db, request.app.state.settings, project_id, user.id, src, src.name,
                                      item.doc_type, item.discipline,
                                      (item.doc_number or "").strip() or number, (item.revision or "").strip() or revision)
            db.commit()   # har fayl alohida saqlanadi: keyingisidagi xato oldingilarini bekor qilmaydi
            results.append({"path": item.path, "status": "imported", "document_id": doc.id,
                            "parse_status": str(doc.parse_status)})
        except service.DuplicateDocument:
            db.rollback()
            results.append({"path": item.path, "status": "duplicate"})
        except OSError:
            db.rollback()
            results.append({"path": item.path, "status": "error", "code": "folder_file_unavailable"})
    audit.record(db, user.id, "project.folder_import", "project", project_id,
                 {"imported": sum(r["status"] == "imported" for r in results), "requested": len(results)})
    db.commit()
    return {"results": results}
