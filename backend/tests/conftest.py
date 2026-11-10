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
    return Settings(data_dir=data, db_url=f"sqlite:///{data / 'engcheck.db'}", encrypt=False)


@pytest.fixture
def db(settings):
    factory = init_db(settings.db_url)
    with factory() as session:
        yield session


@pytest.fixture
def sample_docs(tmp_path):
    from generate_sample_project import generate
    return generate(tmp_path / "sample")


@pytest.fixture
def project(db):
    from engcheck.core.models import Project, Stage
    p = Project(name="Gaz tozalash", industry="gas_processing", stage=Stage.DD)
    db.add(p)
    db.flush()
    return p


@pytest.fixture
def ingest_sample(db, settings, project, sample_docs):
    """Namunaviy loyihaning barcha hujjatlarini yuklaydi; {doc_number: Document}."""
    from engcheck.ingest.service import ingest_file
    return {d.doc_number: ingest_file(db, settings, project.id, None, d.path, d.path.name,
                                      d.doc_type, d.discipline, d.doc_number, d.revision)
            for d in sample_docs}
