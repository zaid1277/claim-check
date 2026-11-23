import httpx
import pytest

from app.core.errors import ProviderError
from app.core.settings import Settings
from app.services.search import BraveSearch


def test_brave_adapter_contract():
    def handler(request):
        assert request.headers["X-Subscription-Token"] == "test"
        return httpx.Response(
            200,
            json={
                "web": {"results": [{"url": "https://example.org", "title": "Example"}]}
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = BraveSearch(
            Settings(_env_file=None, brave_search_api_key="test"), client
        )
        assert provider.search("a claim")[0].title == "Example"


def test_missing_key_is_not_a_fixture_fallback():
    with pytest.raises(ProviderError):
        BraveSearch(Settings(_env_file=None, brave_search_api_key=None)).search("claim")
