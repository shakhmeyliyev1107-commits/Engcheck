"""AI provayderlari: sozlash, kalit, sinash, standart provayder, loyiha uchun joriy rejim."""
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as Db

from ..ai.anthropic_provider import DEFAULT_MODEL
from ..ai.base import AiError
from ..ai.registry import Resolution, resolve, secret_name
from ..core import audit
from ..core.auth import Perm
from ..core.models import AiProvider, Project, User
from .deps import get_db, locale_of, require
from .errors import ApiError, ai_reason

router = APIRouter()
Kind = Literal["anthropic", "openai_compatible", "ollama"]


class NewProvider(BaseModel):
    name: str = Field(min_length=1, max_length=80, pattern=r"\S")
    kind: Kind
    base_url: str | None = None
    model: str | None = None
    embed_model: str | None = None
    api_key: str | None = None


class ProviderPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    base_url: str | None = None
    model: str | None = None
    embed_model: str | None = None
    enabled: bool | None = None
    api_key: str | None = None
    clear_key: bool = False


def resolve_for(request: Request, db: Db, project: Project | None, allow_cloud: bool | None = None) -> Resolution:
    state = request.app.state
    return resolve(db, state.secrets, project, factory=state.provider_factory, allow_cloud=allow_cloud)


def _clean_url(url: str | None, kind: str) -> str | None:
    url = (url or "").strip() or None
    if url is None:
        if kind == "openai_compatible":
            raise ApiError(422, "base_url_required")
        return None
    parts = urlparse(url)
    # Login/parol, so'rov satri yoki fragment bo'lgan manzil qabul qilinmaydi: ular bazada va ro'yxatda ko'rinib qoladi.
    if (parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password
            or parts.query or parts.fragment):
        raise ApiError(422, "base_url_invalid")
    return url.rstrip("/")


def _out(request: Request, row: AiProvider) -> dict:
    state = request.app.state
    try:
        is_local = state.provider_factory(row, None).is_local
    except Exception:
        is_local = False
    return {"id": row.id, "name": row.name, "kind": row.kind, "base_url": row.base_url, "model": row.model,
            "embed_model": row.embed_model, "enabled": row.enabled, "is_default": row.is_default,
            "is_local": is_local, "has_key": state.secrets.get(secret_name(row.id)) is not None}


def _get(db: Db, provider_id: int) -> AiProvider:
    row = db.get(AiProvider, provider_id)
    if row is None:
        raise ApiError(404, "not_found")
    return row


def _name_free(db: Db, name: str, except_id: int | None = None) -> None:
    other = db.query(AiProvider).filter(AiProvider.name == name).first()
    if other is not None and other.id != except_id:
        raise ApiError(409, "name_taken")


@router.get("/ai/providers")
def list_providers(request: Request, _: User = Depends(require(Perm.view)), db: Db = Depends(get_db)):
    return [_out(request, r) for r in db.query(AiProvider).order_by(AiProvider.id)]


@router.post("/ai/providers", status_code=201)
def create_provider(body: NewProvider, request: Request, user: User = Depends(require(Perm.manage_ai)),
                    db: Db = Depends(get_db)):
    name = body.name.strip()
    _name_free(db, name)
    model = (body.model or "").strip() or (DEFAULT_MODEL if body.kind == "anthropic" else None)
    if not model:
        raise ApiError(422, "model_required")
    row = AiProvider(name=name, kind=body.kind, base_url=_clean_url(body.base_url, body.kind), model=model,
                     embed_model=(body.embed_model or "").strip() or None,
                     is_default=db.query(AiProvider).count() == 0)
    db.add(row)
    db.flush()
    if body.api_key:
        request.app.state.secrets.set(secret_name(row.id), body.api_key)
    # Auditga kalitning o'zi emas, faqat borligi yoziladi.
    audit.record(db, user.id, "ai_provider.create", "ai_provider", row.id,
                 {"name": row.name, "kind": row.kind, "base_url": row.base_url, "model": row.model,
                  "key_set": bool(body.api_key)})
    return _out(request, row)


@router.patch("/ai/providers/{provider_id}")
def update_provider(provider_id: int, body: ProviderPatch, request: Request,
                    user: User = Depends(require(Perm.manage_ai)), db: Db = Depends(get_db)):
    row = _get(db, provider_id)
    sent = body.model_fields_set
    if body.name is not None:
        _name_free(db, body.name.strip(), row.id)
        row.name = body.name.strip()
    if "base_url" in sent:
        row.base_url = _clean_url(body.base_url, row.kind)
    if body.model is not None:
        if not body.model.strip():
            raise ApiError(422, "model_required")
        row.model = body.model.strip()
    if "embed_model" in sent:
        row.embed_model = (body.embed_model or "").strip() or None
    if body.enabled is not None:
        row.enabled = body.enabled
    secrets = request.app.state.secrets
    if body.clear_key:
        secrets.delete(secret_name(row.id))
    elif body.api_key:
        secrets.set(secret_name(row.id), body.api_key)
    audit.record(db, user.id, "ai_provider.update", "ai_provider", row.id,
                 {"name": row.name, "base_url": row.base_url, "model": row.model, "enabled": row.enabled,
                  "key_changed": bool(body.api_key) or body.clear_key})
    return _out(request, row)


@router.post("/ai/providers/{provider_id}/default")
def make_default(provider_id: int, request: Request, user: User = Depends(require(Perm.manage_ai)),
                 db: Db = Depends(get_db)):
    row = _get(db, provider_id)
    for other in db.query(AiProvider):
        other.is_default = other.id == row.id
    audit.record(db, user.id, "ai_provider.default", "ai_provider", row.id, {"name": row.name})
    return _out(request, row)


@router.delete("/ai/providers/{provider_id}", status_code=204)
def delete_provider(provider_id: int, request: Request, user: User = Depends(require(Perm.manage_ai)),
                    db: Db = Depends(get_db)):
    row = _get(db, provider_id)
    name = row.name
    request.app.state.secrets.delete(secret_name(row.id))
    db.delete(row)
    audit.record(db, user.id, "ai_provider.delete", "ai_provider", provider_id, {"name": name})
    return Response(status_code=204)


@router.post("/ai/providers/{provider_id}/test")
def test_provider(provider_id: int, request: Request, _: User = Depends(require(Perm.manage_ai)),
                  db: Db = Depends(get_db)):
    row = _get(db, provider_id)
    state = request.app.state
    try:
        state.provider_factory(row, state.secrets.get(secret_name(row.id))).ping()
    except AiError as exc:
        return {"ok": False, "error": exc.code, "message": ai_reason(exc.code, locale_of(request))}
    return {"ok": True, "error": None, "message": None}


@router.get("/projects/{project_id}/ai-status")
def ai_status(project_id: int, request: Request, _: User = Depends(require(Perm.view)),
              db: Db = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise ApiError(404, "not_found")
    r = resolve_for(request, db, project)
    return {"mode": r.mode, "provider": r.provider.name if r.provider else None, "reason": r.reason,
            "message": ai_reason(r.reason, locale_of(request)), "allow_cloud_ai": bool(project.allow_cloud_ai)}
