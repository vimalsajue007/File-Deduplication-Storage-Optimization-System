"""Test fixtures. Runs against in-memory SQLite and eager (inline) Celery — no MySQL/Redis needed."""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="dedupe-tests-")
os.environ.update(
    {
        "DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "CELERY_TASK_ALWAYS_EAGER": "true",
        "UPLOAD_DIR": os.path.join(_TMP, "uploads"),
        "LOG_DIR": os.path.join(_TMP, "logs"),
        "JWT_SECRET_KEY": "test-secret-key-that-is-long-enough-for-hs256",
        "ENVIRONMENT": "test",
        "MAX_UPLOAD_SIZE_MB": "5",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    return TestClient(app)


def register_and_login(client: TestClient, name: str = "alice") -> dict:
    password = "Passw0rd123"
    r = client.post("/api/v1/auth/register", json={"email": f"{name}@example.com", "username": name, "password": password})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/auth/login", data={"username": name, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth(client):
    return register_and_login(client, "alice")


@pytest.fixture
def auth_bob(client):
    return register_and_login(client, "bob")
