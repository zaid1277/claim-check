from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, SecretStr, field_validator

from app.core.settings import get_settings
from app.services.provider_setup import (
    provider_status,
    save_runtime_key,
    server_provider,
)
from app.services.search import make_search

router = APIRouter(tags=["setup"])
_LOCAL = {"localhost", "127.0.0.1", "::1", "[::1]"}


class ProviderKey(BaseModel):
    provider: Literal["tavily", "brave"] = "tavily"
    api_key: SecretStr

    @field_validator("api_key")
    @classmethod
    def valid_key_length(cls, value: SecretStr):
        key = value.get_secret_value().strip()
        if (
            not 1 <= len(key) <= 512
            or not key.isascii()
            or any(c.isspace() for c in key)
        ):
            raise ValueError("Enter a valid API key.")
        return SecretStr(key)


@router.get("/setup/status")
def status(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return provider_status()


@router.post("/setup/providers")
def configure(body: ProviderKey, request: Request):
    settings = get_settings()
    if not settings.allow_runtime_provider_keys or settings.provider_mode != "live":
        raise HTTPException(
            403, "Runtime setup is disabled. Contact the site operator."
        )
    # This opt-in endpoint controls one local process, not individual visitor accounts.
    try:
        origin = urlsplit(request.headers.get("origin", ""))
    except ValueError as exc:
        raise HTTPException(403, "Open setup on localhost.") from exc
    if (
        not request.client
        or request.client.host not in _LOCAL
        or request.url.hostname not in _LOCAL
        or origin.hostname not in _LOCAL
        or origin.scheme not in {"http", "https"}
        or request.headers.get("sec-fetch-site") == "cross-site"
    ):
        raise HTTPException(
            403, "Open setup on localhost to configure this local server."
        )
    if server_provider(settings):
        raise HTTPException(409, "Web search is already configured by the server.")
    field = "tavily_api_key" if body.provider == "tavily" else "brave_search_api_key"
    candidate = settings.model_copy(
        update={
            "search_provider": body.provider,
            field: body.api_key,
            "search_results": 1,
        }
    )
    make_search(candidate).search("web search API documentation")
    save_runtime_key(body.provider, body.api_key)
    return provider_status()
