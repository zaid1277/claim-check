"""Hyper pass, group 2, phase 10: deterministic contradiction assistance.

Real spaCy inference (no mocking, same dependency propositions.py already
uses unconditionally) -- these are the actual alignment checks that will run
in production, not a simulation of them.
"""

from app.services.structured_contradiction import structured_contradiction


def test_matching_revenue_numbers_contradict():
    signal = structured_contradiction(
        "Acme Corp's revenue was $5 billion in 2024.",
        "Acme Corp reported revenue of $8 billion in 2024.",
    )
    assert signal is not None
    assert signal.kind == "numeric"


def test_close_numbers_are_not_flagged():
    # 5.1 vs 5.0 billion is within the "around" tolerance -- not a contradiction.
    signal = structured_contradiction(
        "Acme Corp's revenue was about $5 billion in 2024.",
        "Acme Corp reported revenue of $5.05 billion in 2024.",
    )
    assert signal is None


def test_founding_year_mismatch_contradicts():
    signal = structured_contradiction(
        "Acme Corp was founded in 2003.",
        "Acme Corp was founded in 2004.",
    )
    assert signal is not None
    assert signal.kind == "temporal"


def test_current_claim_is_not_contradicted_by_an_old_year():
    # Phase 12's own example: "is CEO today" vs a historical year must not
    # be flagged as a structural contradiction.
    signal = structured_contradiction(
        "Jane Doe is currently the CEO of Acme Corp.",
        "Jane Doe was CEO of Acme Corp in 2018.",
    )
    assert signal is None


def test_headquarters_location_mismatch_contradicts():
    signal = structured_contradiction(
        "Acme Corp's headquarters are in London.",
        "Acme Corp is headquartered in Berlin.",
    )
    assert signal is not None
    assert signal.kind == "location"


def test_negation_with_high_overlap_contradicts():
    signal = structured_contradiction(
        "Acme Corp acquired Globex Inc.",
        "Acme Corp did not acquire Globex Inc.",
    )
    assert signal is not None
    assert signal.kind == "negation"


def test_topic_only_overlap_is_not_flagged():
    # Same entity, unrelated numbers -- must not fire without predicate alignment.
    signal = structured_contradiction(
        "Acme Corp was founded in 2003.",
        "Acme Corp employs 2004 people across 12 countries.",
    )
    assert signal is None


def test_unrelated_entities_are_not_flagged():
    signal = structured_contradiction(
        "Acme Corp's headquarters are in London.",
        "Globex Inc's headquarters are in Berlin.",
    )
    assert signal is None


def test_no_entity_overlap_no_negation_override_either():
    signal = structured_contradiction(
        "The museum opens on Mondays.",
        "The library closes on Tuesdays.",
    )
    assert signal is None
