"""Do not promote embedded assertions into facts about the reporting actor."""

import pytest

from app.services.propositions import decompose_claim


@pytest.mark.parametrize(
    "claim",
    [
        "The journalist said the company expanded and hired workers.",
        "The report claims the drug works and reduces mortality.",
        "The witness believes the driver stopped and opened the door.",
        "The index rose before trading halted and fell after trading resumed.",
    ],
)
def test_embedded_or_temporally_scoped_claim_stays_intact(claim):
    assert decompose_claim(claim) == [claim]


def test_direct_conjunction_still_preserves_the_actual_actor():
    assert decompose_claim("The company expanded and hired workers.") == [
        "The company expanded.",
        "The company hired workers.",
    ]


def test_pipeline_does_not_classify_an_invented_reporting_actor(monkeypatch):
    from app.core.settings import Settings
    from app.services.article_extraction import Article
    from app.services.pipeline import check_claim
    from app.services.search import FixtureSearch

    claim = "The journalist said the company expanded and hired workers."
    calls = []

    class Embeddings:
        def encode(self, texts):
            return [[1.0, 0.0] for _ in texts]

    class NLI:
        def classify(self, hypothesis, premise):
            calls.append(hypothesis)
            return "neutral", 0.99

    article = Article("https://example.org/report", "Report", "example.org", claim)
    # A follow-up search (hyper pass, phase 15) fires when the first pass
    # finds no usable evidence, which happens here since NLI always returns
    # neutral -- only the first call should return anything, so the
    # follow-up pass legitimately finds nothing further and this test's
    # attribution check still reflects a single real classification.
    collect_calls = []

    def collect_evidence(*args, **kwargs):
        collect_calls.append(kwargs.get("queries"))
        return [(article, claim)] if len(collect_calls) == 1 else []

    monkeypatch.setattr("app.services.pipeline.collect_evidence", collect_evidence)
    monkeypatch.setattr("app.services.pipeline.relevance_score", lambda *args: 10.0)
    result = check_claim(
        claim, Settings(_env_file=None), FixtureSearch([]), Embeddings(), NLI()
    )
    assert calls == [claim]
    assert [atom.claim for atom in result.atomic_claims] == [claim]
