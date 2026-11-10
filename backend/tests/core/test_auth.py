from datetime import timedelta

import pytest

from engcheck.core.auth import Perm, can, create_user, login, logout, user_for_token
from engcheck.core.models import Role, Session, utcnow


@pytest.mark.parametrize("role,perm,expected", [
    (Role.viewer, Perm.view, True), (Role.viewer, Perm.upload, False),
    (Role.viewer, Perm.decide, False),
    (Role.engineer, Perm.upload, True), (Role.engineer, Perm.review, True),
    (Role.engineer, Perm.decide, True), (Role.engineer, Perm.manage_rules, False),
    (Role.engineer, Perm.delete_project, False),
    (Role.lead, Perm.manage_rules, True), (Role.lead, Perm.delete_project, True),
    (Role.lead, Perm.manage_users, False),
    (Role.admin, Perm.manage_users, True), (Role.admin, Perm.decide, True),
])
def test_permission_matrix(role, perm, expected):
    assert can(role, perm) is expected


def test_login_roundtrip_and_hash_not_plain(db):
    u = create_user(db, "aziz", "S3cret-pass", Role.engineer)
    assert "S3cret-pass" not in u.password_hash
    tok = login(db, "aziz", "S3cret-pass")
    assert user_for_token(db, tok).id == u.id
    assert login(db, "aziz", "wrong") is None
    assert login(db, "nobody", "S3cret-pass") is None
    assert db.query(Session).one().token_hash != tok


def test_expired_token_rejected(db):
    create_user(db, "aziz", "S3cret-pass", Role.engineer)
    tok = login(db, "aziz", "S3cret-pass")
    db.query(Session).one().expires_at = utcnow() - timedelta(minutes=1)
    db.flush()
    assert user_for_token(db, tok) is None


def test_inactive_user_cannot_login_or_use_token(db):
    u = create_user(db, "aziz", "S3cret-pass", Role.engineer)
    tok = login(db, "aziz", "S3cret-pass")
    u.is_active = False
    db.flush()
    assert user_for_token(db, tok) is None
    assert login(db, "aziz", "S3cret-pass") is None


def test_logout_invalidates_token(db):
    create_user(db, "aziz", "S3cret-pass", Role.engineer)
    tok = login(db, "aziz", "S3cret-pass")
    logout(db, tok)
    assert user_for_token(db, tok) is None


def test_short_password_rejected(db):
    with pytest.raises(ValueError):
        create_user(db, "aziz", "short", Role.engineer)


def test_duplicate_login_rejected(db):
    create_user(db, "aziz", "S3cret-pass", Role.engineer)
    with pytest.raises(ValueError):
        create_user(db, "aziz", "S3cret-pass2", Role.viewer)
