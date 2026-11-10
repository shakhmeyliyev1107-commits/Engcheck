"""So'rov bog'liqliklari: baza sessiyasi, joriy foydalanuvchi, ruxsat, til."""
from typing import Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session as Db

from ..core import auth
from ..core.auth import Perm
from ..core.models import User
from .errors import ApiError

LOCALES = ("uz", "en", "ru")


def header_locale(request: Request) -> str:
    raw = request.headers.get("accept-language", "")
    for part in raw.split(","):
        code = part.split(";")[0].strip().lower()[:2]
        if code in LOCALES:
            return code
    return "uz"


def get_db(request: Request) -> Iterator[Db]:
    db = request.app.state.session_factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def bearer_token(request: Request) -> str | None:
    value = request.headers.get("authorization", "")
    return value[7:].strip() if value.lower().startswith("bearer ") else None


def current_user(request: Request, db: Db = Depends(get_db)) -> User:
    token = bearer_token(request)
    user = auth.user_for_token(db, token) if token else None
    if user is None:
        raise ApiError(401, "unauthorized")
    request.state.locale = user.locale if user.locale in LOCALES else "uz"
    return user


def require(perm: Perm):
    def checker(user: User = Depends(current_user)) -> User:
        if not auth.can(user.role, perm):
            raise ApiError(403, "forbidden")
        return user
    return checker


def locale_of(request: Request) -> str:
    return getattr(request.state, "locale", None) or header_locale(request)
