"""Baza ulanishi."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def init_db(db_url: str) -> sessionmaker:
    """Jadvallarni yaratadi va sessiya fabrikasini qaytaradi."""
    from . import models  # noqa: F401  (jadvallar ro'yxatdan o'tishi uchun)

    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)
