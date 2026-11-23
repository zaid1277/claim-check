"""Hyper pass (phases 3-7): graded relevance, source-weight recalibration,
softened independence dedup, and claim-risk tiering."""

import pytest

from app.core.settings import Settings
from app.schemas.investigation import Evidence
from app.services.claim_risk import claim_risk
from app.services.evidence_scoring import assess
from app.services.pipeline import relevance_weight_and_directness
from app.services.source_quality import source_quality


@pytest.mark.parametrize(
    "claim,expected",
    [
        ("Paris is the capital of France.", "standard"),
        ("The company was founded in 2005.", "standard"),
        ("Drug X reduces mortality by 30%.", "high"),
        ("The vaccine causes severe side effects.", "high"),
        ("The company's revenue grew to $5 billion.", "high"),
        ("The senator was elected in 2020.", "high"),
        # No risk-domain keyword, but a specific causal+statistic claim is
        # still treated as "high" -- a confident wrong verdict on any precise
        # quantitative causal claim is worth the extra caution, not just
        # medical/financial ones specifically.
        ("Rain increases the risk of delays by 10%.", "high"),
        ("The museum opened in 1990 and closed in 2000.", "standard"),
    ],
)
def test_claim_risk_categories(claim, expected):
    assert claim_risk(claim) == expected


def test_relevance_weight_grades_instead_of_cutting_off():
    settings = Settings(_env_file=None)
    at_floor, _ = relevance_weight_and_directness(settings.relevance_floor, settings)
    just_below, d_below = relevance_weight_and_directness(
        settings.relevance_floor - 0.01, settings
    )
    just_above_floor, d_just_above = relevance_weight_and_directness(
        settings.relevance_floor + 0.1, settings
    )
    mid_band, d_mid = relevance_weight_and_directness(
        1.0, settings
    )  # between floor and knee
    at_knee, d_knee = relevance_weight_and_directness(
        settings.min_proposition_relevance, settings
    )
    above_ceiling, d_above = relevance_weight_and_directness(
        settings.relevance_full_weight + 5, settings
    )
    assert at_floor == 0  # at-or-below the floor is still a hard exclusion
    assert just_below == 0
    assert d_below == "irrelevant"
    # Between the floor and the knee: no longer discarded, but steeply
    # discounted -- this is the band that used to be a hard cliff.
    assert 0 < just_above_floor < mid_band < at_knee < above_ceiling == 1.0
    assert d_just_above == "contextual"
    assert d_mid == "contextual"
    assert d_above == "direct"


def test_wikipedia_is_weighted_above_generic_general_sources():
    settings = Settings(_env_file=None)
    assert (
        source_quality("en.wikipedia.org", settings)[1]
        > source_quality("some-random-blog.example", settings)[1]
    )


def test_second_same_domain_passage_is_discounted_not_discarded():
    settings = Settings(_env_file=None)
    evidence = [
        Evidence(
            title="a",
            url="https://example.org/a",
            domain="example.org",
            passage="Tokyo is Japan's capital.",
            similarity=0.7,
            stance="support",
            stance_confidence=0.9,
            source_weight=0.65,
            evidence_score=0,
            relevance_weight=1.0,
        ),
        Evidence(
            title="b",
            url="https://example.org/b",
            domain="example.org",
            passage="The Japanese government is headquartered in Tokyo.",
            similarity=0.7,
            stance="support",
            stance_confidence=0.9,
            source_weight=0.65,
            evidence_score=0,
            relevance_weight=1.0,
        ),
    ]
    result = assess("Tokyo is the capital of Japan.", evidence, settings)
    counted = [e for e in evidence if e.counted]
    assert len(counted) == 2  # both retained -- the second at a discount, not dropped
    assert result.support_total > max(e.evidence_score for e in counted)
    # still meaningfully less than if the second were full independent weight
    first, second = sorted(counted, key=lambda e: -e.evidence_score)
    assert second.evidence_score == pytest.approx(
        first.evidence_score * settings.duplicate_source_weight, rel=0.05
    )


def test_single_general_source_can_now_clear_the_threshold():
    """The dominant false-abstention pattern from the locked final run: one
    good passage from a general-weighted domain, previously stuck just under
    the 0.5 cliff. With the recalibrated general weight this specific shape
    should now clear it on its own."""
    settings = Settings(_env_file=None)
    evidence = [
        Evidence(
            title="a",
            url="https://example.org/a",
            domain="example.org",
            passage="Tokyo is Japan's capital.",
            similarity=0.8,
            stance="support",
            stance_confidence=0.9,
            source_weight=source_quality("example.org", settings)[1],
            evidence_score=0,
            relevance_weight=1.0,
        ),
    ]
    result = assess("Tokyo is the capital of Japan.", evidence, settings)
    assert result.verdict == "SUPPORTED"
