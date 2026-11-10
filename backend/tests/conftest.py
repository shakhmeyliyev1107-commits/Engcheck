import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "samples"))

from engcheck.config import Settings
from engcheck.core.db import init_db


@pytest.fixture
def settings(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    return Settings(data_dir=data, db_url=f"sqlite:///{data / 'engcheck.db'}")


@pytest.fixture
def db(settings):
    factory = init_db(settings.db_url)
    with factory() as session:
        yield session
