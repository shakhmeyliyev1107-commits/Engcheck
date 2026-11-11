import pytest
from fastapi.testclient import TestClient

from engcheck.api.app import create_app
from engcheck.core.auth import create_user
from engcheck.core.models import Role

PASSWORD = "S3cret-pass"


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app, base_url="http://127.0.0.1") as c:
        yield c


@pytest.fixture
def client_as(app):
    """client_as("engineer") -> shu rol bilan kirgan TestClient."""
    clients = []

    def make(role: str) -> TestClient:
        with app.state.session_factory() as db:
            if not db.query(__import__("engcheck.core.models", fromlist=["User"]).User).filter_by(login=role).first():
                create_user(db, role, PASSWORD, Role(role))
                db.commit()
        c = TestClient(app, base_url="http://127.0.0.1")
        token = c.post("/api/auth/login", json={"login": role, "password": PASSWORD}).json()["token"]
        c.headers["Authorization"] = f"Bearer {token}"
        clients.append(c)
        return c

    yield make
    for c in clients:
        c.close()


@pytest.fixture
def upload():
    def do(client, project_id, d):
        with open(d.path, "rb") as f:
            return client.post(f"/api/projects/{project_id}/documents",
                               files={"file": (d.path.name, f)},
                               data={"doc_type": d.doc_type.value, "discipline": d.discipline.value,
                                     "doc_number": d.doc_number, "revision": d.revision})
    return do


@pytest.fixture
def reviewed(client_as, sample_docs, upload):
    """Namunaviy loyiha yuklangan va tekshirilgan; (engineer client, project_id)."""
    c = client_as("engineer")
    pid = c.post("/api/projects", json={"name": "GP", "industry": "gas_processing", "stage": "DD"}).json()["id"]
    for d in sample_docs:
        assert upload(c, pid, d).status_code == 201
    assert c.post(f"/api/projects/{pid}/reviews").status_code == 201
    return c, pid
