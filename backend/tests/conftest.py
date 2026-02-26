import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine

from app.db import session as session_mod
from app.db.session import get_session
from app.main import app


@pytest.fixture()
def client(monkeypatch):
    # SQLite in-memory for unit tests
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as s:
            yield s

    # Override dependency and engine reference
    app.dependency_overrides[get_session] = override_get_session
    monkeypatch.setattr(session_mod, "engine", engine, raising=False)

    # Patch Celery send_task to no-op during tests
    import app.api.routes.ingest as ingest_mod

    class DummyCelery:
        def send_task(self, *args, **kwargs):
            return None

    ingest_mod.celery_app = DummyCelery()

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
