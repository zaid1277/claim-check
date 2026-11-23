"""Offline article flow with real API routes and a deliberately slow investigation."""

import asyncio

from app.api import inputs
from app.core.settings import get_settings
from app.main import app
from app.services.article_extraction import parse_article

get_settings().provider_mode = "fixture"
get_settings().database_url = None

original_extract_article = inputs.extract_article

ARTICLE = (
    "The Eiffel Tower is in Paris, France. "
    "The tower was built for the 1889 World's Fair. "
    "Gustave Eiffel was an engineer. "
    "The tower stands on the Champ de Mars. "
    "Visitors can climb the Eiffel Tower."
)


def extract_article(url):
    if url != "https://en.wikipedia.org/wiki/Eiffel_Tower":
        return original_extract_article(url)
    return parse_article(
        f"<html><body><article><p>{ARTICLE}</p></article></body></html>", url
    )


inputs.extract_article = extract_article


@app.middleware("http")
async def slow_investigation(request, call_next):
    if request.method == "POST" and request.url.path == "/api/v1/investigations":
        # Cross Next's default 30-second timeout, but stay inside the client budget.
        await asyncio.sleep(31)
    return await call_next(request)
