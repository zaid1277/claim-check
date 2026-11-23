import psycopg
import pytest
from fastapi.testclient import TestClient

from app.api import health
from app.core.settings import Settings, get_settings
from app.main import app


@pytest.fixture
def client():
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, database_url=None
    )
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_liveness_does_not_require_database(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_requires_database_configuration(client):
    assert client.get("/api/v1/ready").status_code == 503


def test_readiness_with_database(client, monkeypatch):
    monkeypatch.setattr(health, "check_database", lambda settings: None)
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


def test_database_errors_are_not_exposed(client, monkeypatch):
    def fail(settings):
        raise psycopg.OperationalError("password=private-test-value")

    monkeypatch.setattr(health, "check_database", fail)
    response = client.get("/api/v1/ready")
    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "DATABASE_UNAVAILABLE",
            "message": "Database is unavailable or not configured.",
        }
    }
    assert "private-test-value" not in response.text
