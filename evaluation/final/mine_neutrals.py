"""Collect development retrieval candidates; labels require passage review."""

import json
from pathlib import Path

from app.core.settings import get_settings
from app.services.collection import collect_evidence
from app.services.embeddings import LocalEmbeddings
from app.services.retrieval import rank_passages
from app.services.search import make_search

ROOT = Path(__file__).resolve().parent
settings = get_settings()
rows = []
for claim in [
    "Grace Hopper was born in 1906.",
    "SpaceX acquired Blue Origin.",
    "Marie Curie won the Nobel Prize in Literature.",
]:
    candidates = collect_evidence(claim, make_search(settings))
    ranked = rank_passages(
        claim,
        [p for _, p in candidates],
        LocalEmbeddings(settings.embedding_model),
        10,
        settings.min_similarity,
    )
    for item in ranked:
        article, passage = candidates[item.index]
        rows.append(
            dict(
                claim=claim,
                passage=passage,
                url=article.url,
                similarity=item.similarity,
            )
        )
    (ROOT / "data/mined-candidates.json").write_text(json.dumps(rows, indent=2) + "\n")
    print("Collected", len(ranked), "development candidates", flush=True)
