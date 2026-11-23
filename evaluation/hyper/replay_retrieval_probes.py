"""Query-aware replay for the retrieval probe set (source diversity, retrieval
depth, two-sided evidence, follow-up search). Unlike replay_controlled.py's
FixtureSearch (which ignores the query text and always returns every source),
this fixture returns different results per query string, so it can actually
exercise query-dependent behavior like a follow-up search.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "api"))

from app.core.settings import Settings  # noqa: E402
from app.services import article_extraction, pipeline, search  # noqa: E402
from app.services.embeddings import LocalEmbeddings  # noqa: E402
from app.services.nli import LocalNLI  # noqa: E402

PROBES = json.loads((REPO / "evaluation/hyper/data/retrieval-probes.json").read_text())


class QueryAwareSearch:
    """Exact match for the standard search_queries() variants; word-overlap
    match against follow_up_results for anything else, since a generated
    follow-up query's exact wording is not meant to be hand-predicted --
    this mirrors how a real search engine tolerates reworded queries."""

    def __init__(self, query_map, follow_up_results=()):
        self.query_map = query_map
        self.follow_up_results = follow_up_results

    def search(self, query):
        if query in self.query_map:
            return [
                search.SearchResult(r["url"], "Probe source")
                for r in self.query_map[query]
            ]
        lowered = query.casefold()
        for group in self.follow_up_results:
            if all(w.casefold() in lowered for w in group["trigger_words"]):
                return [
                    search.SearchResult(r["url"], "Probe source")
                    for r in group["results"]
                ]
        return []


def run(
    top_k=None, max_per_domain=None, follow_up=None, max_sources=None, probes=PROBES
):
    settings = Settings(_env_file=None)
    settings.provider_mode = "live"
    if top_k is not None:
        settings.top_k = top_k
    if max_per_domain is not None:
        settings.max_candidates_per_domain = max_per_domain
    if follow_up is not None:
        settings.allow_follow_up_search = follow_up
    if max_sources is not None:
        settings.max_sources = max_sources
    embeddings = LocalEmbeddings(settings.embedding_model)
    nli = LocalNLI(settings.nli_model, settings.min_nli_confidence)
    results = []
    for probe in probes:
        url_to_passage = {
            r["url"]: r for rows in probe["queries"].values() for r in rows
        }
        for group in probe.get("follow_up_results", ()):
            url_to_passage.update({r["url"]: r for r in group["results"]})

        def fetch(url, url_to_passage=url_to_passage):
            text = url_to_passage[url]["passage"]
            html = (
                f"<html><head><title>doc</title></head>"
                f"<body><article><p>{text}</p></article></body></html>"
            )
            return html, url

        def make_search(configuration, probe=probe):
            return QueryAwareSearch(
                probe["queries"], probe.get("follow_up_results", ())
            )

        original_fetch, original_search = (
            article_extraction.fetch_html,
            search.make_search,
        )
        article_extraction.fetch_html = fetch
        search.make_search = make_search
        try:
            assessment = pipeline.check_claim(
                probe["claim"], settings, search.make_search(settings), embeddings, nli
            )
        finally:
            article_extraction.fetch_html, search.make_search = (
                original_fetch,
                original_search,
            )
        results.append(
            {
                "id": probe["id"],
                "kind": probe["kind"],
                "expected": probe["expected"],
                "predicted": assessment.verdict,
                "n_evidence": len(assessment.evidence),
                "n_domains": len({e.domain for e in assessment.evidence if e.counted}),
                "correct": assessment.verdict == probe["expected"],
            }
        )
    return results


if __name__ == "__main__":
    results = run()
    for r in results:
        print(r)
    correct = sum(1 for r in results if r["correct"])
    print(f"\n{correct}/{len(results)} correct")
