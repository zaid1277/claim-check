import pytest

from app.core.settings import Settings
from app.schemas.investigation import Evidence
from app.services.evidence_scoring import aggregate, assess
from app.services.source_quality import source_quality


@pytest.mark.parametrize(
    "s,c,expected",
    [
        (0, 0, "INSUFFICIENT_EVIDENCE"),
        (0.5, 0, "SUPPORTED"),
        (0, 0.5, "UNSUPPORTED"),
        (0.5, 0.5, "MIXED_EVIDENCE"),
        (1, 0.5, "SUPPORTED"),
    ],
)
def test_verdict_boundaries(s, c, expected):
    assert aggregate(s, c, 2, Settings(_env_file=None), "standard") == expected


@pytest.mark.parametrize(
    "s,c,sources,expected",
    [
        # A high-risk claim needs the (higher) high-risk minimum-evidence floor.
        (0.7, 0, 2, "SUPPORTED"),
        (0.6, 0, 2, "INSUFFICIENT_EVIDENCE"),
        # ...and at least two independent sources, even with plenty of total weight.
        (0.9, 0, 1, "INSUFFICIENT_EVIDENCE"),
        (0.9, 0, 2, "SUPPORTED"),
    ],
)
def test_high_risk_requires_more_evidence_and_sources(s, c, sources, expected):
    assert aggregate(s, c, sources, Settings(_env_file=None), "high") == expected


def test_neutral_does_not_count_as_support():
    e = Evidence(
        title="fixture",
        url="https://example.org",
        domain="example.org",
        passage="fixture",
        similarity=0.8,
        stance="neutral",
        stance_confidence=0.9,
        source_weight=0.75,
        evidence_score=0,
    )
    result = assess("claim", [e], Settings(_env_file=None))
    assert e.evidence_score == pytest.approx(0.8 * 0.9 * 0.75)
    assert result.support_total == result.contradict_total == 0


def test_source_domain_boundary():
    settings = Settings(_env_file=None)
    assert source_quality("www.cdc.gov", settings) == ("official", 0.95)
    assert source_quality("reuters.com.attacker.example", settings) == ("general", 0.70)
    assert source_quality("en.wikipedia.org", settings) == ("encyclopedia", 0.75)
