import os
import tempfile
from pathlib import Path, PurePosixPath, PureWindowsPath

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session as Db, joinedload

from ..core.auth import Perm
from ..core.models import Discipline, DocPage, DocType, Document, TagParam, User
from ..ingest import service
from ..review.rules.base import active_ids
from .deps import get_db, locale_of, require
from .errors import ApiError
from .routes_projects import get_project
from .serializers import document_out, param_name

router = APIRouter()


def get_document(db: Db, document_id: int) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise ApiError(404, "not_found")
    return doc


def safe_filename(name: str | None) -> str:
    """Yo'l qismlarini olib tashlaydi: '../../x.dwg' -> 'x.dwg'."""
    base = PureWindowsPath(PurePosixPath(name or "").name).name.strip()
    return base[:255] or "file"


@router.get("/doc-type-suggestion")
def suggestion(filename: str, _: User = Depends(require(Perm.view))):
    doc_type = service.suggest_doc_type(filename)
    number, revision = service.suggest_number_revision(filename)
    return {"doc_type": doc_type.value if doc_type else None, "doc_number": number, "revision": revision}


@router.get("/projects/{project_id}/documents")
def list_documents(project_id: int, request: Request, _: User = Depends(require(Perm.view)),
                   db: Db = Depends(get_db)):
    get_project(db, project_id)
    docs = db.query(Document).filter_by(project_id=project_id).order_by(Document.id)
    active = active_ids(db, project_id)
    return [document_out(d, locale_of(request), active) for d in docs]


@router.post("/projects/{project_id}/documents", status_code=201)
def upload_document(project_id: int, request: Request, file: UploadFile = File(...),
                    doc_type: DocType = Form(...), discipline: Discipline = Form(...),
                    doc_number: str | None = Form(None), revision: str | None = Form(None),
                    user: User = Depends(require(Perm.upload)), db: Db = Depends(get_db)):
    get_project(db, project_id)
    filename = safe_filename(file.filename)
    fd, tmp = tempfile.mkstemp(suffix=Path(filename).suffix)
    try:
        with os.fdopen(fd, "wb") as out:
            while chunk := file.file.read(1 << 20):
                out.write(chunk)
        try:
            doc = service.ingest_file(db, request.app.state.settings, project_id, user.id, Path(tmp),
                                      filename, doc_type, discipline,
                                      (doc_number or "").strip() or None, (revision or "").strip() or None)
        except service.DuplicateDocument as exc:
            raise ApiError(409, "duplicate_document") from exc
    finally:
        Path(tmp).unlink(missing_ok=True)
    return document_out(doc, locale_of(request))


@router.get("/documents/{document_id}")
def read_document(document_id: int, request: Request, _: User = Depends(require(Perm.view)),
                  db: Db = Depends(get_db)):
    doc = get_document(db, document_id)
    locale = locale_of(request)
    out = document_out(doc, locale, active_ids(db, doc.project_id))
    out["unmapped_headers"] = doc.unmapped_headers or []
    out["skipped_tags"] = doc.skipped_tags or []
    out["pages"] = [{"page_no": p.page_no, "text": p.text} for p in
                    db.query(DocPage).filter_by(document_id=doc.id).order_by(DocPage.page_no)]
    params = (db.query(TagParam).filter_by(document_id=doc.id).options(joinedload(TagParam.tag))
              .order_by(TagParam.page_no, TagParam.id))
    out["params"] = [{"tag": p.tag.tag, "param": p.param, "param_name": param_name(p.param, locale),
                      "raw_value": p.raw_value, "raw_unit": p.raw_unit, "si_value": p.si_value,
                      "si_unit": p.si_unit, "page_no": p.page_no, "location": p.location,
                      "method": str(p.method), "confidence": str(p.confidence)} for p in params]
    return out


@router.get("/documents/{document_id}/file")
def download_document(document_id: int, _: User = Depends(require(Perm.view)), db: Db = Depends(get_db)):
    doc = get_document(db, document_id)
    if not doc.stored_path or not Path(doc.stored_path).is_file():
        raise ApiError(404, "not_found")
    return FileResponse(doc.stored_path, filename=doc.filename)


@router.delete("/documents/{document_id}", status_code=204)
def remove_document(document_id: int, request: Request, user: User = Depends(require(Perm.upload)),
                    db: Db = Depends(get_db)):
    get_document(db, document_id)
    service.delete_document(db, request.app.state.settings, document_id, user.id)
    return Response(status_code=204)
