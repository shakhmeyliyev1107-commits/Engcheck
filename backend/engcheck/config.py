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

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"


def get_settings() -> Settings:
    data_dir = Path(os.environ.get("ENGCHECK_DATA_DIR", Path.home() / ".engcheck")).expanduser()
    data_dir.mkdir(parents=True, exist_ok=True)
    port = int(os.environ.get("ENGCHECK_PORT", "8765"))
    return Settings(data_dir=data_dir, db_url=f"sqlite:///{data_dir / 'engcheck.db'}", port=port)
