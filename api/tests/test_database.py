import os

import pytest
from fastapi.testclient import TestClient

from app.core.settings import Settings, get_settings
from app.main import app


@pytest.mark.integration
def test_readiness_against_postgresql():
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to run the PostgreSQL smoke test")

    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, database_url=database_url
    )
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready", "database": "ok"}
    finally:
        app.dependency_overrides.clear()
