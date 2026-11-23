from datetime import UTC, datetime
from uuid import uuid4

from app.schemas.investigation import Assessment, Evidence, Investigation

DEMO_CLAIM = "The demonstration library opens on Sundays."


def fixture_investigation(claim: str) -> Investigation:
    """Return a clearly labelled fixture, never simulated live research."""
    evidence = []
    if claim.casefold() == DEMO_CLAIM.casefold():
        evidence = [
            Evidence(
                title="Fictional library schedule — test fixture",
                url="https://example.com/fixture-library",
                domain="example.com",
                passage=(
                    "The demonstration library is open on Sundays from 10:00 to 16:00."
                ),
                similarity=1,
                stance="support",
                stance_confidence=1,
                evidence_score=0.55,
            )
        ]
    assessment = Assessment(
        claim=claim,
        verdict="SUPPORTED" if evidence else "INSUFFICIENT_EVIDENCE",
        explanation=(
            "The fictional schedule explicitly lists Sunday opening hours. [1]"
            if evidence
            else "No fixture evidence is available for this claim."
        ),
        support_total=0.55 if evidence else 0,
        evidence=evidence,
    )
    return Investigation(
        id=uuid4(),
        created_at=datetime.now(UTC),
        mode="fixture",
        raw_text=claim,
        assessments=[assessment],
        model_metadata={"provider": "deterministic fixture"},
    )


def investigate(claim: str) -> Investigation:
    from app.services.embeddings import LocalEmbeddings
    from app.services.nli import LocalNLI
    from app.services.pipeline import check_claim
    from app.services.provider_setup import search_settings
    from app.services.search import make_search

    settings = search_settings()
    if settings.provider_mode == "fixture":
        return fixture_investigation(claim)
    assessment = check_claim(
        claim,
        settings,
        make_search(settings),
        LocalEmbeddings(settings.embedding_model),
        LocalNLI(settings.nli_model, settings.min_nli_confidence),
    )
    return Investigation(
        id=uuid4(),
        created_at=datetime.now(UTC),
        mode="live",
        raw_text=claim,
        assessments=[assessment],
        model_metadata={
            "search": str(settings.search_provider),
            "embeddings": settings.embedding_model,
            "nli": settings.nli_model,
            "proposition_relevance": settings.proposition_model,
            "min_proposition_relevance": str(settings.min_proposition_relevance),
            "min_similarity": str(settings.min_similarity),
            "min_nli_confidence": str(settings.min_nli_confidence),
            "minimum_evidence": str(settings.minimum_evidence),
            "min_contradiction_confidence": str(settings.min_contradiction_confidence),
            "max_atomic_claims": str(settings.max_atomic_claims),
            "duplicate_similarity": str(settings.duplicate_similarity),
            "current_evidence_days": str(settings.current_evidence_days),
            "dominance_ratio": str(settings.dominance_ratio),
        },
    )
