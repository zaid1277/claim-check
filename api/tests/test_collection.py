import pytest

from app.core.errors import ProviderError
from app.services.article_extraction import Article
from app.services.collection import collect_evidence
from app.services.search import FixtureSearch, SearchResult


def test_unreadable_sources_and_empty_search_do_not_invent_passages():
    def unreadable(url):
        raise ProviderError("Unreadable")

    search = FixtureSearch([SearchResult("https://example.org", "fixture")])
    assert collect_evidence("claim", search, extract=unreadable) == []
    assert collect_evidence("claim", FixtureSearch([])) == []


def test_search_failure_stops_collection():
    class FailingSearch:
        def search(self, query):
            raise ProviderError("Search failed")

    with pytest.raises(ProviderError):
        collect_evidence("claim", FailingSearch())


def test_passage_budget_and_source_deduplication():
    fetched = []

    def extract(url):
        fetched.append(url)
        return Article(url, "fixture", "example.org", "word " * 200)

    search = FixtureSearch([SearchResult("https://example.org", "fixture")])
    assert (
        len(
            collect_evidence(
                "claim", search, extract=extract, passage_words=20, max_passages=3
            )
        )
        == 3
    )
    assert fetched == ["https://example.org"]
