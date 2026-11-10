from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session as Db

from ..core import audit, auth
from ..core.auth import Perm
from ..core.models import Role, User
from .deps import bearer_token, current_user, get_db, require
from .errors import ApiError
from .serializers import user_out

router = APIRouter()
Locale = Literal["uz", "en", "ru"]


class Credentials(BaseModel):
    login: str
    password: str


class NewUser(Credentials):
    role: Role
    locale: Locale = "uz"


class UserPatch(BaseModel):
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = None


class MePatch(BaseModel):
    locale: Locale


def _create(db: Db, login: str, password: str, role: Role, locale: str = "uz") -> User:
    try:
        return auth.create_user(db, login, password, role, locale)
    except ValueError as exc:
        code = str(exc)
        raise ApiError(409 if code == "login_taken" else 422, code) from exc


@router.get("/setup")
def setup_status(db: Db = Depends(get_db)):
    return {"needs_setup": db.query(User).count() == 0}


@router.post("/setup", status_code=201)
def setup(body: Credentials, db: Db = Depends(get_db)):
    if db.query(User).count() > 0:
        raise ApiError(409, "setup_done")
    user = _create(db, body.login, body.password, Role.admin)
    audit.record(db, user.id, "setup.admin_created", "user", user.id, {"login": user.login})
    return user_out(user)


@router.post("/auth/login")
def login(body: Credentials, db: Db = Depends(get_db)):
    token = auth.login(db, body.login, body.password)
    if token is None:
        raise ApiError(401, "bad_credentials")
    user = auth.user_for_token(db, token)
    audit.record(db, user.id, "auth.login", "user", user.id)
    return {"token": token, "user": user_out(user)}


@router.post("/auth/logout", status_code=204)
def logout(request: Request, user: User = Depends(current_user), db: Db = Depends(get_db)):
    auth.logout(db, bearer_token(request))
    return Response(status_code=204)


@router.get("/auth/me")
def me(user: User = Depends(current_user)):
    return user_out(user)


@router.patch("/auth/me")
def update_me(body: MePatch, request: Request, user: User = Depends(current_user),
              db: Db = Depends(get_db)):
    user.locale = body.locale
    request.state.locale = body.locale
    return user_out(user)


@router.get("/users")
def list_users(_: User = Depends(require(Perm.manage_users)), db: Db = Depends(get_db)):
    return [user_out(u) for u in db.query(User).order_by(User.id)]


@router.post("/users", status_code=201)
def create_user(body: NewUser, admin: User = Depends(require(Perm.manage_users)),
                db: Db = Depends(get_db)):
    user = _create(db, body.login, body.password, body.role, body.locale)
    audit.record(db, admin.id, "user.create", "user", user.id, {"login": user.login, "role": str(user.role)})
    return user_out(user)


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserPatch, admin: User = Depends(require(Perm.manage_users)),
                db: Db = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(404, "not_found")
    demotes = (body.role is not None and body.role != Role.admin) or body.is_active is False
    if user.role == Role.admin and user.is_active and demotes:
        others = db.query(User).filter(User.role == Role.admin, User.is_active.is_(True),
                                       User.id != user.id).count()
        if others == 0:
            raise ApiError(409, "last_admin")
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.password is not None:
        try:
            auth.set_password(db, user, body.password)
        except ValueError as exc:
            raise ApiError(422, str(exc)) from exc
    audit.record(db, admin.id, "user.update", "user", user.id,
                 {"role": str(user.role), "is_active": user.is_active,
                  "password_changed": body.password is not None})
    return user_out(user)
