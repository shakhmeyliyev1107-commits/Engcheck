"""Foydalanuvchilar, sessiyalar va rol ruxsatlari."""
import hashlib
import secrets
from datetime import timedelta
from enum import StrEnum

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy.orm import Session as Db

from .models import Role, Session, User, utcnow

SESSION_TTL = timedelta(hours=12)
MIN_PASSWORD_LEN = 8
_hasher = PasswordHasher()


class Perm(StrEnum):
    view = "view"
    upload = "upload"
    review = "review"
    decide = "decide"
    manage_rules = "manage_rules"
    delete_project = "delete_project"
    manage_users = "manage_users"
    manage_kb = "manage_kb"
    manage_ai = "manage_ai"
    link_folder = "link_folder"


_ENGINEER = {Perm.view, Perm.upload, Perm.review, Perm.decide}
_LEAD = _ENGINEER | {Perm.manage_rules, Perm.delete_project, Perm.manage_kb, Perm.link_folder}
_MATRIX: dict[Role, set[Perm]] = {
    Role.viewer: {Perm.view},
    Role.engineer: _ENGINEER,
    Role.lead: _LEAD,
    Role.admin: _LEAD | {Perm.manage_users, Perm.manage_ai},
}


def can(role: Role, perm: Perm) -> bool:
    return perm in _MATRIX[Role(role)]


def hash_password(password: str) -> str:
    if len(password) < MIN_PASSWORD_LEN:
        raise ValueError("password_too_short")
    return _hasher.hash(password)


def create_user(db: Db, login: str, password: str, role: Role, locale: str = "uz") -> User:
    login = login.strip()
    if not login:
        raise ValueError("login_empty")
    if db.query(User).filter(User.login == login).first():
        raise ValueError("login_taken")
    user = User(login=login, password_hash=hash_password(password), role=Role(role), locale=locale)
    db.add(user)
    db.flush()
    return user


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def login(db: Db, login: str, password: str) -> str | None:
    user = db.query(User).filter(User.login == login.strip()).first()
    if user is None or not user.is_active:
        return None
    try:
        _hasher.verify(user.password_hash, password)
    except (VerificationError, InvalidHashError):
        return None
    token = secrets.token_urlsafe(32)
    db.add(Session(token_hash=_token_hash(token), user_id=user.id, expires_at=utcnow() + SESSION_TTL))
    db.flush()
    return token


def user_for_token(db: Db, token: str) -> User | None:
    sess = db.query(Session).filter(Session.token_hash == _token_hash(token)).first()
    if sess is None or sess.expires_at <= utcnow():
        return None
    user = db.get(User, sess.user_id)
    return user if user is not None and user.is_active else None


def logout(db: Db, token: str) -> None:
    db.query(Session).filter(Session.token_hash == _token_hash(token)).delete()
    db.flush()


def set_password(db: Db, user: User, password: str) -> None:
    """Parolni almashtiradi va foydalanuvchining barcha sessiyalarini bekor qiladi."""
    user.password_hash = hash_password(password)
    db.query(Session).filter(Session.user_id == user.id).delete()
    db.flush()
