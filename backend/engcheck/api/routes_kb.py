"""Bilimlar bazasi: manbalar, qidiruv, indekslash."""
import os
import tempfile
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session as Db

from ..ai.base import AiError
from ..core import audit
from ..core.auth import Perm
from ..core.models import KbSource, User
from ..kb import service
from .deps import get_db, locale_of, require
from .errors import ApiError, ai_reason
from .routes_ai import resolve_for
from .routes_documents import safe_filename
from .serializers import kb_source_out

router = APIRouter()
Kind = Literal["standard", "literature", "note", "lesson"]
Status = Literal["active", "superseded", "withdrawn"]
License = Literal["licensed", "open", "internal"]


class SourcePatch(BaseModel):
    title: str | None = None
    standard_code: str | None = None
    edition: str | None = None
    status: Status | None = None
    license_type: License | None = None
    approved: bool | None = None


class ReindexBody(BaseModel):
    allow_cloud: bool = False


def _users(db: Db) -> dict[int, str]:
    return {u.id: u.login for u in db.query(User)}


@router.get("/kb/sources")
def list_sources(_: User = Depends(require(Perm.view)), db: Db = Depends(get_db)):
    users = _users(db)
    return [kb_source_out(s, users) for s in db.query(KbSource).order_by(KbSource.id.desc())]


@router.post("/kb/sources", status_code=201)
def add_source(request: Request, title: str = Form(..., min_length=1, max_length=255), kind: Kind = Form(...),
               text: str | None = Form(None), standard_code: str | None = Form(None),
               edition: str | None = Form(None), status: Status = Form("active"),
               license_type: License = Form("internal"), file: UploadFile | None = File(None),
               user: User = Depends(require(Perm.upload)), db: Db = Depends(get_db)):
    settings = request.app.state.settings
    common = dict(standard_code=standard_code, edition=edition, status=status, license_type=license_type)
    tmp = None
    try:
        if file is not None and file.filename:
            filename = safe_filename(file.filename)
            fd, tmp = tempfile.mkstemp(suffix=Path(filename).suffix)
            with os.fdopen(fd, "wb") as out:
                while chunk := file.file.read(1 << 20):
                    out.write(chunk)
            source = service.add_source(db, settings, user, title, kind, path=Path(tmp), filename=filename, **common)
        else:
            source = service.add_source(db, settings, user, title, kind, text=text or "", **common)
    except service.KbError as exc:
        raise ApiError(409 if exc.code == "duplicate" else 422,
                       f"kb_{exc.code}" if exc.code != "invalid" else "validation_error", detail="title") from exc
    finally:
        if tmp:
            Path(tmp).unlink(missing_ok=True)
    return kb_source_out(source, {user.id: user.login})


@router.patch("/kb/sources/{source_id}")
def update_source(source_id: int, body: SourcePatch, user: User = Depends(require(Perm.manage_kb)),
                  db: Db = Depends(get_db)):
    source = db.get(KbSource, source_id)
    if source is None:
        raise ApiError(404, "not_found")
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        if field == "approved":
            source.approved = bool(value)
            source.approved_by = user.id if value else None
        elif field == "title":
            if value and value.strip():
                source.title = value.strip()
        else:
            setattr(source, field, value or None if field in ("standard_code", "edition") else value)
    audit.record(db, user.id, "kb.update", "kb_source", source.id, changes)
    return kb_source_out(source, _users(db))


@router.delete("/kb/sources/{source_id}", status_code=204)
def delete_source(source_id: int, request: Request, user: User = Depends(require(Perm.manage_kb)),
                  db: Db = Depends(get_db)):
    if db.get(KbSource, source_id) is None:
        raise ApiError(404, "not_found")
    service.delete_source(db, request.app.state.settings, source_id, user.id)
    return Response(status_code=204)


@router.get("/kb/search")
def search(request: Request, q: str = Query(..., min_length=1, max_length=500), k: int = Query(5, ge=1, le=20),
           _: User = Depends(require(Perm.view)), db: Db = Depends(get_db)):
    """Qidiruv natijasi: iqtibos va manba ma'lumoti. Litsenziyali manbaning to'liq matni qaytarilmaydi."""
    provider = resolve_for(request, db, None, allow_cloud=False).provider   # faqat lokal embedding
    return [{"chunk_id": h.chunk_id, "source_id": h.source_id, "title": h.title, "kind": h.kind,
             "standard_code": h.standard_code, "edition": h.edition, "status": h.status,
             "license_type": h.license_type, "page_no": h.page_no, "excerpt": h.excerpt}
            for h in service.search(db, q, k, provider)]


@router.post("/kb/reindex")
def reindex(body: ReindexBody, request: Request, user: User = Depends(require(Perm.manage_kb)),
            db: Db = Depends(get_db)):
    """Embedding indeksini quradi. Bulutli provayder faqat aniq ruxsat bilan; litsenziyali matn bulutga yuborilmaydi."""
    locale = locale_of(request)
    resolution = resolve_for(request, db, None, allow_cloud=body.allow_cloud)
    if resolution.provider is None:
        raise ApiError(503, "ai_unavailable", reason=ai_reason(resolution.reason, locale))
    if not resolution.provider.embed_model:
        raise ApiError(422, "embeddings_unsupported")
    try:
        count = service.reindex(db, resolution.provider)
    except AiError as exc:
        raise ApiError(503, "ai_unavailable", reason=ai_reason(exc.code, locale)) from exc
    audit.record(db, user.id, "kb.reindex", "kb_source", None,
                 {"provider": resolution.provider.name, "mode": resolution.mode, "chunks": count})
    return {"indexed": count, "provider": resolution.provider.name, "mode": resolution.mode}
