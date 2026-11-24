"""Source diversity must keep a source's best passages, not its first ones."""

from app.core.settings import Settings
from app.services import pipeline
from app.services.article_extraction import Article
from app.services.search import FixtureSearch


class FixedEmbeddings:
    def encode(self, texts):
        return [[1.0, 0.0] if "schedule" in text else [0.0, 1.0] for text in texts]


class SupportingNLI:
    def classify(self, claim, passage):
        return "support", 0.99


def test_relevant_later_passage_survives_domain_cap(monkeypatch):
    article = Article("https://example.org/library", "Library", "example.org", "")
    candidates = [(article, f"Unrelated introductory paragraph {i}.") for i in range(3)]
    candidates.append((article, "The library schedule includes Sunday opening."))
    monkeypatch.setattr(pipeline, "collect_evidence", lambda *a, **kw: candidates)
    monkeypatch.setattr(
        pipeline, "gate_stance", lambda *a: ("support", None, 4.0, "direct", 1.0)
    )
    result = pipeline.check_atomic(
        "The library schedule includes Sunday opening.",
        Settings(_env_file=None, allow_follow_up_search=False),
        FixtureSearch([]),
        FixedEmbeddings(),
        SupportingNLI(),
    )
    assert result.verdict == "SUPPORTED"
    assert len(result.evidence) == 1
    assert "schedule" in result.evidence[0].passage


def test_domain_cap_refills_top_k_from_other_sources(monkeypatch):
    candidates = [
        (Article(f"https://a.org/{i}", "A", "a.org", ""), f"schedule detail {i}")
        for i in range(3)
    ] + [(Article("https://b.org/1", "B", "b.org", ""), "schedule independent detail")]
    monkeypatch.setattr(pipeline, "collect_evidence", lambda *a, **kw: candidates)
    monkeypatch.setattr(
        pipeline, "gate_stance", lambda *a: ("support", None, 4.0, "direct", 1.0)
    )
    evidence = pipeline._gather_evidence(
        "The schedule includes Sunday opening.",
        Settings(_env_file=None, top_k=3, max_candidates_per_domain=2),
        FixtureSearch([]),
        FixedEmbeddings(),
        SupportingNLI(),
    )
    assert [item.url for item in evidence] == [
        "https://a.org/0",
        "https://a.org/1",
        "https://b.org/1",
    ]
