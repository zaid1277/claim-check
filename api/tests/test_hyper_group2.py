"""Hyper pass, group 2: source diversity, retrieval depth, and follow-up
search regressions."""

from app.core.settings import Settings
from app.schemas.investigation import Evidence
from app.services.evidence_scoring import assess
from app.services.search import follow_up_query, search_queries


def _evidence(url, domain, similarity=0.7, stance="support", weight=0.65):
    return Evidence(
        title="t",
        url=url,
        domain=domain,
        passage=f"passage from {url}",
        similarity=similarity,
        stance=stance,
        stance_confidence=0.9,
        source_weight=weight,
        evidence_score=0,
        relevance_weight=1.0,
    )


def test_third_passage_from_same_domain_gets_no_further_credit():
    """A single domain repeating itself three times should not be able to
    manufacture unbounded support -- see GROUP1/2 diversity probe finding."""
    settings = Settings(_env_file=None)
    evidence = [
        _evidence("https://a.example/1", "a.example"),
        _evidence("https://a.example/2", "a.example"),
        _evidence("https://a.example/3", "a.example"),
    ]
    assess("claim", evidence, settings)
    counted = [e for e in evidence if e.counted]
    assert len(counted) == 2  # first at full weight, second discounted, third excluded
    third = evidence[2]
    assert not third.counted


def test_one_strong_independent_source_can_still_outweigh_repeated_domain():
    """The bug this fix specifically closed: a syndicated domain repeating
    itself must not be able to out-vote one genuinely independent,
    contradicting source purely on volume."""
    settings = Settings(_env_file=None)
    evidence = [
        _evidence("https://wire.example/1", "wire.example", stance="support"),
        _evidence("https://wire.example/2", "wire.example", stance="support"),
        _evidence("https://wire.example/3", "wire.example", stance="support"),
        _evidence("https://wire.example/4", "wire.example", stance="support"),
        _evidence(
            "https://registry.example/1",
            "registry.example",
            stance="contradict",
            similarity=0.75,
        ),
    ]
    result = assess("claim", evidence, settings)
    assert result.verdict != "SUPPORTED"  # must not be a confident wrong verdict


def test_follow_up_query_differs_from_standard_queries():
    claim = "Vantage Systems acquired Corelux in 2021."
    query = follow_up_query(claim)
    assert query is not None
    assert query not in search_queries(claim)
    # Should retain the substantive terms, not just echo the claim verbatim.
    lowered = query.casefold()
    assert "vantage" in lowered or "corelux" in lowered


def test_follow_up_query_drops_generic_scaffolding():
    query = follow_up_query("The company was founded in 2003.")
    assert query is not None
    # Common stopword-ish scaffolding shouldn't dominate a short, targeted query.
    assert len(query.split()) <= 6
