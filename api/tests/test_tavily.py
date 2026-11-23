import httpx
import pytest
from pydantic import SecretStr, ValidationError

from app.core.errors import ProviderError
from app.core.settings import Settings, get_settings
from app.services import provider_setup
from app.services.search import FixtureSearch, TavilySearch, make_search


def test_normalized_tavily_search():
    def respond(request):
        assert request.method == "POST"
        assert request.headers["Authorization"] == "Bearer test-example"
        import json

        body = json.loads(request.content)
        assert body["search_depth"] == "basic"
        assert not body["include_answer"]
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://example.org",
                        "title": "Source",
                        "content": "A source excerpt",
                        "score": 0.8,
                    }
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = TavilySearch(
            Settings(_env_file=None, tavily_api_key="test-example"), client
        ).search("a claim")[0]
    assert (result.title, result.url, result.snippet, result.provider_score) == (
        "Source",
        "https://example.org",
        "A source excerpt",
        0.8,
    )


@pytest.mark.parametrize(
    "code,message",
    [
        (401, "rejected"),
        (429, "usage limit"),
        (432, "usage limit"),
        (500, "unavailable"),
    ],
)
def test_tavily_safe_http_errors(code, message):
    with httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(code))
    ) as client:
        with pytest.raises(ProviderError, match=message):
            TavilySearch(
                Settings(_env_file=None, tavily_api_key="test-example"), client
            ).search("claim")


def test_tavily_timeout():
    def respond(request):
        raise httpx.ReadTimeout("private upstream details")

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(ProviderError, match="too long"):
            TavilySearch(
                Settings(_env_file=None, tavily_api_key="test-example"), client
            ).search("claim")


def test_tavily_empty_results():
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(200, json={"results": []})
        )
    ) as client:
        assert (
            TavilySearch(
                Settings(_env_file=None, tavily_api_key="test-example"), client
            ).search("claim")
            == []
        )


@pytest.mark.parametrize("payload", [{}, {"results": [{}]}, {"results": "bad"}])
def test_tavily_malformed_response(payload):
    with httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload))
    ) as client:
        with pytest.raises(ProviderError):
            TavilySearch(
                Settings(_env_file=None, tavily_api_key="test-example"), client
            ).search("claim")


@pytest.mark.parametrize(
    "explicit,tavily,brave,expected",
    [
        (None, None, None, "tavily"),
        (None, "t", None, "tavily"),
        (None, None, "b", "brave"),
        (None, "t", "b", "tavily"),
        ("brave", "t", "b", "brave"),
        ("tavily", None, "b", "brave"),
        ("mock", None, None, "mock"),
    ],
)
def test_provider_resolution(monkeypatch, explicit, tavily, brave, expected):
    s = get_settings()
    monkeypatch.setattr(s, "search_provider", explicit)
    monkeypatch.setattr(s, "tavily_api_key", SecretStr(tavily) if tavily else None)
    monkeypatch.setattr(s, "brave_search_api_key", SecretStr(brave) if brave else None)
    monkeypatch.setattr(s, "allow_runtime_provider_keys", False)
    assert provider_setup.search_settings().search_provider == expected


def test_mock_cannot_be_selected_for_live_mode():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, provider_mode="live", search_provider="mock")
    assert isinstance(
        make_search(Settings(_env_file=None, search_provider="mock")), FixtureSearch
    )


def test_runtime_tavily_validation(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    s = get_settings()
    for name, value in {
        "provider_mode": "live",
        "search_provider": None,
        "tavily_api_key": None,
        "brave_search_api_key": None,
        "allow_runtime_provider_keys": True,
        "database_url": "postgresql://localhost/test",
    }.items():
        monkeypatch.setattr(s, name, value)
    monkeypatch.setattr(provider_setup, "_runtime", None)
    monkeypatch.setattr(provider_setup, "_rejected", {})
    monkeypatch.setattr(TavilySearch, "search", lambda self, query: [])
    with TestClient(
        app, base_url="http://localhost", client=("127.0.0.1", 8000)
    ) as client:
        response = client.post(
            "/api/v1/setup/providers",
            headers={"Origin": "http://localhost:3000"},
            json={"provider": "tavily", "api_key": "local-example"},
        )
        assert response.status_code == 200
        assert response.json()["ready"]
        assert response.json()["providers"]["search"]["provider"] == "tavily"
        assert "local-example" not in response.text
    assert (
        provider_setup.search_settings().tavily_api_key.get_secret_value()
        == "local-example"
    )
    assert s.tavily_api_key is None
