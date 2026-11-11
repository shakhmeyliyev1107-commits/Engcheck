"""Bazani SQLCipher bilan shifrlash: ochish, holatni aniqlash, ochiq bazani ko'chirish."""
import secrets
import shutil
import sqlite3
from pathlib import Path

from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import sessionmaker

from ..config import Settings
from .db import init_db
from .secrets import SecretStore

KEY_NAME = "db_key"
PLAIN_HEADER = b"SQLite format 3\x00"


class DatabaseLocked(Exception):
    """Baza shifrlangan, lekin kalit yoki sqlcipher3 yo'q — ochib bo'lmaydi."""


class AlreadyEncrypted(Exception):
    pass


class EncryptionUnavailable(Exception):
    pass


def sqlcipher_module():
    try:
        import sqlcipher3
        return sqlcipher3
    except ImportError:
        return None


def available() -> bool:
    return sqlcipher_module() is not None


def is_plain(path: Path) -> bool:
    with open(path, "rb") as f:
        return f.read(16) == PLAIN_HEADER


def open_database(settings: Settings, store: SecretStore) -> tuple[sessionmaker, bool]:
    """(sessiya fabrikasi, shifrlanganmi).

    - Mavjud ochiq baza ochiq holicha ochiladi (jim o'zgartirilmaydi; `encrypt-db` buyrug'i ko'chiradi).
    - Mavjud shifrlangan baza kalit bilan ochiladi; kalit yo'q bo'lsa DatabaseLocked.
    - Yangi baza: shifrlash yoqilgan va sqlcipher3 mavjud bo'lsa — shifrlangan.
    """
    path, module = settings.db_path, sqlcipher_module()
    exists = path.exists() and path.stat().st_size > 0
    if not exists and any(path.with_name(path.name + ext).exists() for ext in (".encrypting", ".plain.bak")):
        # encrypt-db o'rtada uzilgan: bo'sh yangi baza yaratib, eski ma'lumotni "yo'qotib" qo'ymaymiz.
        raise DatabaseLocked("bazani shifrlash tugallanmagan: engcheck.db.plain.bak faylini engcheck.db ga qaytaring")
    if exists and is_plain(path):
        return init_db(settings.db_url), False
    if exists:
        key = store.get(KEY_NAME)
        if module is None or not key:
            raise DatabaseLocked("baza shifrlangan, lekin kalit yoki sqlcipher3 topilmadi")
        try:
            return init_db(settings.db_url, key, module), True
        except DatabaseError as exc:
            raise DatabaseLocked("baza kaliti mos kelmadi") from exc
    if settings.encrypt and module is not None:
        key = store.get(KEY_NAME)
        if not key:
            key = secrets.token_hex(32)
            store.set(KEY_NAME, key)
        return init_db(settings.db_url, key, module), True
    return init_db(settings.db_url), False


def encrypt_database(settings: Settings, store: SecretStore) -> Path:
    """Ochiq bazani shifrlangan nusxaga ko'chiradi. Asl fayl `.plain.bak` nomi bilan qoladi.

    Zaxira nusxani foydalanuvchi tekshirib, o'zi o'chiradi — dastur ma'lumotni o'chirmaydi.
    """
    path, module = settings.db_path, sqlcipher_module()
    if module is None:
        raise EncryptionUnavailable("sqlcipher3 o'rnatilmagan")
    if not path.exists():
        raise FileNotFoundError(path)
    if not is_plain(path):
        raise AlreadyEncrypted(str(path))
    key = store.get(KEY_NAME) or secrets.token_hex(32)
    store.set(KEY_NAME, key)
    target = path.with_name(path.name + ".encrypting")
    backup = path.with_name(path.name + ".plain.bak")
    target.unlink(missing_ok=True)
    try:
        con = module.connect(str(path))
        try:
            con.execute("ATTACH DATABASE ? AS encrypted KEY ?", (str(target), f"x'{key}'"))
            con.execute("SELECT sqlcipher_export('encrypted')")
            con.execute("DETACH DATABASE encrypted")
        finally:
            con.close()
        _verify(path, target, key, module)
    except BaseException:
        target.unlink(missing_ok=True)   # asl baza joyida, o'zgarmagan holda qoladi
        raise
    # Avval ochiq nusxa zaxiraga nusxalanadi, keyin BITTA atomik almashtirish: istalgan paytda uzilsa ham
    # engcheck.db yo ochiq, yo shifrlangan to'liq baza bo'ladi.
    shutil.copy2(path, backup)
    target.replace(path)
    return backup


def _verify(plain: Path, encrypted: Path, key: str, module) -> None:
    """Har jadvaldagi qatorlar soni mos kelishini tekshiradi; mos kelmasa asl baza joyida qoladi."""
    a = sqlite3.connect(plain)
    b = module.connect(str(encrypted))
    try:
        b.execute(f"""PRAGMA key = "x'{key}'" """)
        tables = [r[0] for r in a.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for table in tables:
            left = a.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
            right = b.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
            if left != right:
                raise RuntimeError(f"shifrlangan nusxa mos kelmadi: {table}")
    finally:
        a.close(); b.close()
