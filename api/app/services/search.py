from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.errors import ProviderError
from app.core.settings import Settings


@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str = ""
    provider_score: float | None = None


class SearchProvider(Protocol):
    def search(self, query: str) -> list[SearchResult]: ...


class BraveSearch:
    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self.settings = settings
        self.client = client

    def search(self, query: str) -> list[SearchResult]:
        """Query Brave without falling back to invented evidence."""
        if not self.settings.brave_search_api_key:
            raise ProviderError("Live search is not configured.")
        key = self.settings.brave_search_api_key.get_secret_value()
        try:
            with httpx.Client(timeout=15, trust_env=False) as default_client:
                response = (self.client or default_client).get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": query, "count": self.settings.search_results},
                    headers={"X-Subscription-Token": key},
                )
                response.raise_for_status()
                return [
                    SearchResult(url=item["url"], title=item["title"])
                    for item in response.json().get("web", {}).get("results", [])
                ]
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403}:
                from app.services.provider_setup import reject_key

                reject_key("brave", self.settings.brave_search_api_key)
                raise ProviderError("Brave Search rejected this API key.") from exc
            if exc.response.status_code == 429:
                raise ProviderError(
                    "Brave Search quota is exhausted. Try again later."
                ) from exc
            raise ProviderError(
                "Web search is temporarily unavailable. Try again later."
            ) from exc
        except httpx.TimeoutException as exc:
            raise ProviderError("Web search took too long. Please try again.") from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise ProviderError(
                "Search is unavailable. Please try again later."
            ) from exc


class TavilySearch:
    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self.settings = settings
        self.client = client

    def search(self, query: str) -> list[SearchResult]:
        if not self.settings.tavily_api_key:
            raise ProviderError("Tavily search is not configured.")
        try:
            with httpx.Client(timeout=15, trust_env=False) as default_client:
                response = (self.client or default_client).post(
                    "https://api.tavily.com/search",
                    headers={
                        "Authorization": "Bearer "
                        + self.settings.tavily_api_key.get_secret_value()
                    },
                    json={
                        "query": query,
                        "max_results": self.settings.search_results,
                        "search_depth": "basic",
                        "include_answer": False,
                        "include_raw_content": False,
                        "include_images": False,
                        "auto_parameters": False,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict) or not isinstance(
                    payload.get("results"), list
                ):
                    raise ValueError("Invalid search response")
                results = []
                for item in payload["results"]:
                    if (
                        not isinstance(item, dict)
                        or not isinstance(item.get("url"), str)
                        or not isinstance(item.get("title"), str)
                    ):
                        raise ValueError("Invalid search result")
                    score = item.get("score")
                    results.append(
                        SearchResult(
                            url=item["url"],
                            title=item["title"],
                            snippet=item.get("content")
                            if isinstance(item.get("content"), str)
                            else "",
                            provider_score=float(score)
                            if isinstance(score, (int, float))
                            else None,
                        )
                    )
                return results
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {401, 403}:
                from app.services.provider_setup import reject_key

                reject_key("tavily", self.settings.tavily_api_key)
                raise ProviderError("Tavily rejected this API key.") from exc
            if exc.response.status_code in {429, 432, 433}:
                raise ProviderError(
                    "Tavily's usage limit was reached. Try again later."
                ) from exc
            raise ProviderError(
                "Tavily is temporarily unavailable. Try again later."
            ) from exc
        except httpx.TimeoutException as exc:
            raise ProviderError(
                "Tavily took too long to respond. Please try again."
            ) from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise ProviderError(
                "Tavily could not be reached or read. Please try again."
            ) from exc


class FixtureSearch:
    def __init__(self, results: list[SearchResult]):
        self.results = results

    def search(self, query: str) -> list[SearchResult]:
        return list(self.results)


def search_queries(claim: str) -> list[str]:
    return [claim, f"{claim} evidence research", f"{claim} official statistics"]


def follow_up_query(claim: str) -> str | None:
    """A targeted second-pass query built from entities/numbers/dates and
    remaining content words, dropping generic scaffolding (hyper pass, group
    2, phase 15). Deterministic -- no search-agent LLM. Returns None if the
    claim doesn't decompose into anything more specific than the claim itself
    (e.g. already very short)."""
    from app.services.propositions import parser

    doc = parser()(claim)
    keep_labels = {
        "PERSON",
        "ORG",
        "GPE",
        "NORP",
        "FAC",
        "DATE",
        "MONEY",
        "PERCENT",
        "CARDINAL",
        "PRODUCT",
        "EVENT",
    }
    entity_spans = {(e.start, e.end) for e in doc.ents if e.label_ in keep_labels}
    covered = {i for start, end in entity_spans for i in range(start, end)}
    terms = []
    seen = set()
    for token in doc:
        if token.i in covered:
            continue  # entity text is appended as a whole, separately, below
        if token.pos_ in {"NOUN", "PROPN", "VERB"} and not token.is_stop:
            lemma = token.lemma_.casefold()
            if lemma not in seen:
                seen.add(lemma)
                terms.append(token.text)
    entity_terms = []
    for ent in doc.ents:
        if ent.label_ in keep_labels and ent.text.casefold() not in seen:
            seen.add(ent.text.casefold())
            entity_terms.append(ent.text)
    query = " ".join(entity_terms + terms).strip()
    return query or None


def make_search(settings: Settings) -> SearchProvider:
    if settings.search_provider == "brave":
        return BraveSearch(settings)
    if settings.search_provider == "mock":
        if settings.provider_mode != "fixture":
            raise ProviderError("Mock search is unavailable for live investigations.")
        return FixtureSearch([])
    return TavilySearch(settings)
