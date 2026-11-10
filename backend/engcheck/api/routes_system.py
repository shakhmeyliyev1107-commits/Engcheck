"""Tizim holati: ma'lumotlar qanday himoyalangani (administrator uchun)."""
from fastapi import APIRouter, Depends, Request

from ..core import dbcrypt
from ..core.auth import Perm
from ..core.models import User
from .deps import require

router = APIRouter()
VERSION = "0.3.0"


@router.get("/system")
def system(request: Request, _: User = Depends(require(Perm.manage_users))):
    state = request.app.state
    return {"version": VERSION, "db_encrypted": bool(state.db_encrypted),
            "encryption_available": dbcrypt.available(), "secret_backend": state.secrets.backend,
            "files_encrypted": False}
