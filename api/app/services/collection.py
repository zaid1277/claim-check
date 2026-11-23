from collections.abc import Callable
from itertools import zip_longest

from app.core.errors import ProviderError
from app.services.article_extraction import Article, extract_article, make_passages
from app.services.search import SearchProvider, search_queries


def collect_evidence(
    claim: str,
    search: SearchProvider,
    extract: Callable[[str], Article] = extract_article,
    max_sources: int = 10,
    passage_words: int = 100,
    max_passages: int = 100,
    queries: list[str] | None = None,
) -> list[tuple[Article, str]]:
    """Keep search failures visible; skip individual unreadable sources.

    `queries` overrides the standard search_queries(claim) list -- used for a
    single targeted follow-up query (hyper pass, phase 15).
    """
    seen: set[str] = set()
    sources = []
    for query in queries if queries is not None else search_queries(claim):
        if len(seen) >= max_sources:
            break
        for result in search.search(query):
            if result.url in seen or len(seen) >= max_sources:
                continue
            seen.add(result.url)
            try:
                article = extract(result.url)
            except ProviderError:
                continue
            sources.append(
                [(article, text) for text in make_passages(article.text, passage_words)]
            )
    # Give every fetched source a turn before taking a second chunk from one page.
    passages = []
    for group in zip_longest(*sources):
        for item in group:
            if item is not None:
                passages.append(item)
                if len(passages) == max_passages:
                    return passages
    return passages
