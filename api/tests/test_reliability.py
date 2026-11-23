"""Controlled regressions for evidence eligibility and compound coverage."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.core.settings import Settings
from app.services.article_extraction import Article, make_passages
from app.services.independence import source_group
from app.services.pipeline import check_claim, gate_stance
from app.services.propositions import decompose_claim
from app.services.search import FixtureSearch


@pytest.mark.parametrize(
    "text",
    [
        "The museum may open and close in June.",
        "The museum did not open and close in June.",
        "The museum contains paintings and sculptures.",
    ],
)
def test_ambiguous_scope_stays_intact(text):
    assert decompose_claim(text) == [text]


def test_decomposition_preserves_subject_and_resolves_explicit_pronoun():
    assert decompose_claim(
        "The company earned $10 billion in 2024 and employed 50,000 people."
    ) == [
        "The company earned $10 billion in 2024.",
        "The company employed 50,000 people.",
    ]
    assert decompose_claim("The museum opened in 1990 and it closed in 2000.") == [
        "The museum opened in 1990.",
        "The museum closed in 2000.",
    ]


@pytest.fixture(autouse=True)
def fixed_relevance(monkeypatch):
    # Pipeline mechanics tests inject relevance; real model tests cover inference.
    monkeypatch.setattr("app.services.pipeline.relevance_score", lambda *args: 10.0)


def test_opposite_predicate_is_not_rejected_by_literal_matching():
    settings = Settings(_env_file=None)
    stance, reason, *_ = gate_stance(
        "The museum opens on Mondays.",
        "The museum is closed on Mondays.",
        "contradict",
        0.99,
        None,
        settings,
    )
    assert stance == "contradict"
    assert reason is None


def test_topic_only_evidence_is_excluded_in_both_directions(monkeypatch):
    # Below relevance_floor (0.0): still a hard exclusion, not just a discount.
    monkeypatch.setattr("app.services.pipeline.relevance_score", lambda *args: -3.0)
    for raw in ["support", "contradict"]:
        stance, reason, score, directness, weight = gate_stance(
            "The museum opens on Mondays.",
            "The museum stores paintings.",
            raw,
            0.99,
            None,
            Settings(_env_file=None),
        )
        assert stance == "neutral"
        assert "Proposition relevance" in reason
        assert weight == 0
        assert directness == "irrelevant"


def test_currentness_and_confidence_are_not_truth():
    settings = Settings(_env_file=None)
    assert (
        gate_stance(
            "The museum currently has ten rooms.",
            "The museum has ten rooms.",
            "support",
            0.99,
            None,
            settings,
        )[0]
        == "neutral"
    )
    date = datetime.now(UTC).date().isoformat()
    assert (
        gate_stance(
            "The museum currently has ten rooms.",
            "The museum has ten rooms.",
            "support",
            0.99,
            date,
            settings,
        )[0]
        == "support"
    )
    # Below settings.min_contradiction_confidence (hyper pass, group 3:
    # lowered to 0.70 after a validated precision-recall sweep) -- use a
    # confidence clearly under that gate, not a value that happens to sit
    # exactly on a threshold this test doesn't own.
    assert (
        gate_stance(
            "The museum opened in 1990.",
            "The museum opened in 1991.",
            "contradict",
            0.5,
            None,
            settings,
        )[0]
        == "neutral"
    )


class Embeddings:
    def encode(self, texts):
        return [[1.0, 0.0] for _ in texts]


class NLI:
    def classify(self, claim, passage):
        return ("support", 0.99) if claim == passage else ("neutral", 0.99)


def test_complete_pipeline_requires_all_atoms_and_deduplicates(monkeypatch):
    original = "The museum opened in 1990 and it closed in 2000."
    atoms = decompose_claim(original)
    candidates = [
        (Article(f"https://museum.gov/{i}", "Museum", "museum.gov", p), p)
        for i, p in enumerate(atoms)
    ]
    monkeypatch.setattr(
        "app.services.pipeline.collect_evidence", lambda *a, **k: candidates
    )
    result = check_claim(
        original, Settings(_env_file=None), FixtureSearch([]), Embeddings(), NLI()
    )
    assert result.claim == original
    assert result.verdict == "SUPPORTED"
    assert len(result.atomic_claims) == 2
    assert all(a.verdict == "SUPPORTED" for a in result.atomic_claims)
    candidates.pop()
    partial = check_claim(
        original, Settings(_env_file=None), FixtureSearch([]), Embeddings(), NLI()
    )
    assert partial.verdict == "INSUFFICIENT_EVIDENCE"
    candidates.extend(candidates * 8)
    repeated = check_claim(
        atoms[0], Settings(_env_file=None), FixtureSearch([]), Embeddings(), NLI()
    )
    assert len(repeated.evidence) == 1
    assert repeated.support_total < 1


def test_registrable_domain_groups_subdomains():
    assert source_group("https://news.example.co.uk/a") == source_group(
        "https://www.example.co.uk/b"
    )
    assert source_group("https://other.co.uk") != source_group("https://example.co.uk")


def test_sentences_are_not_cut_at_word_budget():
    passage = "The museum opened in 1990. It closed in 2000. The library remains open."
    chunks = make_passages(passage, 10)
    assert chunks[0] == "The museum opened in 1990. It closed in 2000."


def test_frozen_benchmark_has_disjoint_groups_and_valid_hashes():
    root = Path(__file__).resolve().parents[2] / "evaluation/reliability/data"
    manifest = json.loads((root / "manifest.json").read_text())
    for name, digest in manifest.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
    for name, minimum in [("nli", 120), ("retrieval", 30), ("verdicts", 50)]:
        rows = json.loads((root / f"{name}.json").read_text())
        assert len(rows) >= minimum
        groups = {
            s: {r["group"] for r in rows if r["split"] == s}
            for s in ["development", "validation", "test"]
        }
        assert not groups["development"] & groups["test"]
        assert not groups["validation"] & groups["test"]
        assert not groups["development"] & groups["validation"]
