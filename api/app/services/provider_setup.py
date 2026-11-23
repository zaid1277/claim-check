from threading import Lock
from typing import Literal

from pydantic import SecretStr

from app.core.settings import Settings, get_settings

_lock = Lock()
_runtime: tuple[str, SecretStr] | None = None
_rejected: dict[str, SecretStr] = {}


def save_runtime_key(provider: str, key: SecretStr) -> None:
    global _runtime
    with _lock:
        _runtime = (provider, key)
        _rejected.pop(provider, None)


def reject_key(provider: str, key: SecretStr) -> None:
    with _lock:
        _rejected[provider] = key


def server_provider(settings: Settings) -> Literal["tavily", "brave", "mock"] | None:
    if settings.search_provider == "mock":
        return "mock"
    keys = {"tavily": settings.tavily_api_key, "brave": settings.brave_search_api_key}
    if settings.search_provider and keys[settings.search_provider]:
        return settings.search_provider
    if settings.tavily_api_key:
        return "tavily"
    if settings.brave_search_api_key:
        return "brave"
    return None


def search_settings() -> Settings:
    settings = get_settings()
    provider = server_provider(settings)
    if provider:
        return settings.model_copy(update={"search_provider": provider})
    with _lock:
        runtime = _runtime if settings.allow_runtime_provider_keys else None
    if runtime:
        provider, key = runtime
        field = "tavily_api_key" if provider == "tavily" else "brave_search_api_key"
        return settings.model_copy(update={"search_provider": provider, field: key})
    return settings.model_copy(
        update={"search_provider": settings.search_provider or "tavily"}
    )


def provider_status():
    settings = search_settings()
    provider = settings.search_provider
    key = (
        settings.tavily_api_key
        if provider == "tavily"
        else settings.brave_search_api_key
    )
    with _lock:
        configured = bool(key) and key != _rejected.get(provider)
    fixture = settings.provider_mode == "fixture"
    return {
        "ready": fixture or (configured and bool(settings.database_url)),
        "mode": settings.provider_mode,
        "runtime_keys_allowed": settings.allow_runtime_provider_keys
        and not fixture
        and server_provider(get_settings()) is None,
        "database_configured": bool(settings.database_url),
        "providers": {"search": {"configured": configured, "provider": provider}},
    }
