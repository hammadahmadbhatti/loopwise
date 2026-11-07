"""Test setup: isolated SQLite DB per test, offline AI only, no background worker."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="loopwise-tests-")
os.environ.update({
    "DATABASE_URL": f"sqlite:///{_TMP}/import-time.db",
    "WORKER_ENABLED": "false",
    "AUTO_MIGRATE": "false",
    "AI_PROVIDER": "heuristic",  # never call paid APIs from tests, even if keys are set
    "EMBEDDINGS_PROVIDER": "local",
    "EMAIL_MODE": "outbox",
    "OUTBOX_DIR": f"{_TMP}/outbox",
    "SECRET_KEY": "test-secret",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.ai import embeddings, registry  # noqa: E402
from app.db import get_db, make_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.routers import public  # noqa: E402
from app.services.analysis import drain  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def session_factory(tmp_path):
    """Fresh database per test: SQLite by default, or Postgres when TEST_DATABASE_URL is set."""
    url = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tmp_path}/test.db"
    engine = make_engine(url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    if url.startswith("postgresql"):
        Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(session_factory):
    def _get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    public._hits.clear()
    embeddings.set_embedder(None)
    registry._INSTANCES.clear()
    with TestClient(app) as c:
        c.session_factory = session_factory  # type: ignore[attr-defined]
        yield c
    app.dependency_overrides.clear()
    registry._INSTANCES.clear()


class Account:
    def __init__(self, client: TestClient, email: str, workspace: str):
        r = client.post("/api/auth/register", json={"email": email, "password": "correct-horse-1", "name": email.split("@")[0].title(), "workspace_name": workspace})
        assert r.status_code == 201, r.text
        data = r.json()
        self.client = client
        self.token = data["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.wid = data["user"]["workspaces"][0]["id"]
        self.base = f"/api/workspaces/{self.wid}"

    def get(self, path: str, **kw):
        return self.client.get(self.base + path, headers=self.headers, **kw)

    def post(self, path: str, **kw):
        return self.client.post(self.base + path, headers=self.headers, **kw)

    def patch(self, path: str, **kw):
        return self.client.patch(self.base + path, headers=self.headers, **kw)

    def delete(self, path: str, **kw):
        return self.client.delete(self.base + path, headers=self.headers, **kw)

    def drain(self) -> int:
        with self.client.session_factory() as db:  # type: ignore[attr-defined]
            return drain(db)

    def import_sample(self) -> dict:
        with open(FIXTURES / "sample_feedback.csv", "rb") as fh:
            r = self.post("/feedback/import", files={"file": ("sample.csv", fh, "text/csv")})
        assert r.status_code == 200, r.text
        return r.json()


@pytest.fixture
def account(client) -> Account:
    return Account(client, "owner@acme.example.com", "Acme Analytics")


@pytest.fixture
def loaded(account) -> Account:
    """Account with the 76-row multilingual sample imported and analyzed."""
    assert account.import_sample()["imported"] == 76
    account.drain()
    return account
