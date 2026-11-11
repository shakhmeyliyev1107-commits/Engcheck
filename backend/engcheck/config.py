"""Ilova sozlamalari."""
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    data_dir: Path
    db_url: str
    host: str = "127.0.0.1"
    port: int = 8765
    encrypt: bool = True          # sqlcipher3 mavjud bo'lsa, yangi baza shifrlangan holda yaratiladi
    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost", "[::1]")

    @property
    def db_path(self) -> Path:
        return Path(self.db_url.removeprefix("sqlite:///"))

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"


def get_settings(data_dir: str | Path | None = None, port: int | None = None) -> Settings:
    data_dir = Path(data_dir or os.environ.get("ENGCHECK_DATA_DIR", Path.home() / ".engcheck")).expanduser()
    data_dir.mkdir(parents=True, exist_ok=True)
    if port is None:
        port = int(os.environ.get("ENGCHECK_PORT", "8765"))
    encrypt = os.environ.get("ENGCHECK_ENCRYPT", "1") != "0"
    return Settings(data_dir=data_dir, db_url=f"sqlite:///{data_dir / 'engcheck.db'}", port=port, encrypt=encrypt)
