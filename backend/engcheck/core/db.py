"""Baza ulanishi."""
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import QueuePool


class Base(DeclarativeBase):
    pass


def init_db(db_url: str, key: str | None = None, module=None) -> sessionmaker:
    """Jadvallarni yaratadi va sessiya fabrikasini qaytaradi.

    key va module (sqlcipher3) berilsa, baza SQLCipher bilan shifrlangan holda ochiladi.
    """
    from . import models  # noqa: F401  (jadvallar ro'yxatdan o'tishi uchun)

    if key is not None:
        from sqlalchemy.engine import URL
        path = db_url.removeprefix("sqlite:///")
        # Kalit — tasodifiy 256 bit, "xom kalit" ko'rinishida beriladi: har ulanishda parol hisobi (KDF) bajarilmaydi.
        url = URL.create("sqlite+pysqlcipher", password=f"x'{key}'", database=path)
        # QueuePool aniq ko'rsatiladi: bu dialektning standart hovuzi oqimlar ko'payganda ishlatilayotgan ulanishni yopib qo'yadi.
        engine = create_engine(url, module=module, poolclass=QueuePool, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(db_url, poolclass=QueuePool, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    add_missing_columns(engine)
    return sessionmaker(engine, expire_on_commit=False)


def add_missing_columns(engine) -> list[str]:
    """Oldingi versiya bazasiga yangi ustunlarni qo'shadi (ma'lumot saqlanadi).

    Faqat ustun qo'shadi; mavjud ustunni o'zgartirmaydi yoki o'chirmaydi.
    """
    added = []
    inspector = inspect(engine)
    with engine.begin() as con:
        for table in Base.metadata.sorted_tables:
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column.type.compile(engine.dialect)}'
                if column.server_default is not None:
                    ddl += f" DEFAULT {column.server_default.arg!s}"
                con.execute(text(ddl))
                added.append(f"{table.name}.{column.name}")
    return added
