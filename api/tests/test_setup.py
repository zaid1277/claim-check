import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.settings import get_settings
from app.main import app
from app.services import provider_setup
from app.services.search import BraveSearch


@pytest.fixture
def local(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "provider_mode", "live")
    monkeypatch.setattr(settings, "allow_runtime_provider_keys", True)
    monkeypatch.setattr(settings, "brave_search_api_key", None)
    monkeypatch.setattr(settings, "tavily_api_key", None)
    monkeypatch.setattr(settings, "search_provider", None)
    monkeypatch.setattr(settings, "database_url", "postgresql://localhost/test")
    monkeypatch.setattr(provider_setup, "_runtime", None)
    monkeypatch.setattr(provider_setup, "_rejected", {})
    with TestClient(
        app,
        base_url="http://localhost",
        client=("127.0.0.1", 9000),
        headers={"Origin": "http://localhost:3000"},
    ) as client:
        yield client


def test_status_has_no_secrets(local, monkeypatch):
    monkeypatch.setattr(
        get_settings(), "brave_search_api_key", SecretStr("private-example")
    )
    response = local.get("/api/v1/setup/status")
    assert response.json()["ready"]
    assert "private-example" not in response.text
    assert not response.json()["runtime_keys_allowed"]


def test_validated_runtime_key_is_used_without_mutating_environment(local, monkeypatch):
    monkeypatch.setattr(BraveSearch, "search", lambda self, query: [])
    response = local.post(
        "/api/v1/setup/providers",
        json={"provider": "brave", "api_key": "local-example"},
    )
    assert response.status_code == 200
    assert response.json()["ready"]
    assert "local-example" not in response.text
    assert (
        provider_setup.search_settings().brave_search_api_key.get_secret_value()
        == "local-example"
    )
    assert get_settings().brave_search_api_key is None


@pytest.mark.parametrize(
    "origin", ["https://evil.example", "null", "", "http://[broken"]
)
def test_cross_origin_setup_is_rejected(local, origin):
    assert (
        local.post(
            "/api/v1/setup/providers",
            headers={"Origin": origin},
            json={"provider": "brave", "api_key": "example"},
        ).status_code
        == 403
    )


def test_disabled_setup(local, monkeypatch):
    monkeypatch.setattr(get_settings(), "allow_runtime_provider_keys", False)
    assert (
        local.post(
            "/api/v1/setup/providers", json={"provider": "brave", "api_key": "example"}
        ).status_code
        == 403
    )


def test_invalid_key_is_not_saved(local, monkeypatch):
    original_search = BraveSearch.search

    def reject(self, query):
        with httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(401))
        ) as client:
            return original_search(BraveSearch(self.settings, client), query)

    monkeypatch.setattr(BraveSearch, "search", reject)
    response = local.post(
        "/api/v1/setup/providers",
        json={"provider": "brave", "api_key": "invalid-example"},
    )
    assert response.status_code == 502
    assert response.json()["error"]["message"] == "Brave Search rejected this API key."
    assert "invalid-example" not in response.text
    assert provider_setup.search_settings().brave_search_api_key is None


def test_revoked_runtime_key_returns_to_setup(local):
    provider_setup.save_runtime_key("brave", SecretStr("expired-example"))
    provider_setup.reject_key("brave", SecretStr("expired-example"))
    assert not local.get("/api/v1/setup/status").json()["ready"]


def test_remote_peer_is_rejected(local):
    with TestClient(
        app, base_url="http://localhost", client=("203.0.113.2", 1234)
    ) as client:
        response = client.post(
            "/api/v1/setup/providers",
            headers={"Origin": "http://localhost:3000"},
            json={"provider": "brave", "api_key": "example"},
        )
        assert response.status_code == 403
