from app.core.settings import Settings
from app.services.article_extraction import Article
from app.services.pipeline import check_claim
from app.services.search import FixtureSearch


def test_pipeline_preserves_passage_and_citation_metadata(monkeypatch):
    article = Article("https://example.org", "Fixture", "example.org", "", "2026-01-01")
    monkeypatch.setattr(
        "app.services.pipeline.collect_evidence",
        lambda *a, **k: [(article, "The museum did not open in 1990.")],
    )

    class Embeddings:
        def encode(self, texts):
            return [[1, 0], [1, 0]]

    class NLI:
        def classify(self, claim, passage):
            assert passage == "The museum did not open in 1990."
            return "contradict", 1.0

    result = check_claim(
        "The museum opened in 1990.",
        Settings(_env_file=None),
        FixtureSearch([]),
        Embeddings(),
        NLI(),
    )
    assert result.verdict == "UNSUPPORTED"
    assert result.evidence[0].published_at == "2026-01-01"
    assert "[1]" in result.explanation
    assert "The museum did not open in 1990." in result.explanation


def test_eiffel_support_survives_scoring_and_serialization(monkeypatch):
    from app.schemas.investigation import Assessment

    claim = "The Eiffel Tower is in Paris."
    passage = (
        "The Eiffel Tower is a wrought-iron lattice tower "
        "on the Champ de Mars in Paris, France."
    )
    article = Article("https://example.org", "Fixture", "example.org", passage)
    monkeypatch.setattr(
        "app.services.pipeline.collect_evidence", lambda *a, **k: [(article, passage)]
    )

    class Embeddings:
        def encode(self, texts):
            assert texts == [claim, passage]
            return [[1, 0], [1, 0]]

    class NLI:
        def classify(self, hypothesis, premise):
            assert (hypothesis, premise) == (claim, passage)
            return "support", 0.99

    result = check_claim(
        claim, Settings(_env_file=None), FixtureSearch([]), Embeddings(), NLI()
    )
    restored = Assessment.model_validate_json(result.model_dump_json())
    assert restored.verdict == "SUPPORTED"
    assert restored.evidence[0].stance == "support"
    assert restored.support_total > 0.5
    assert restored.contradict_total == 0
