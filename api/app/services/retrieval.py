import math
from dataclasses import dataclass

from app.services.embeddings import EmbeddingProvider


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Compare direction, returning zero when either vector has no magnitude."""
    if len(left) != len(right) or not left:
        raise ValueError("Vectors must have the same nonzero dimension.")
    if not all(math.isfinite(x) for x in left + right):
        raise ValueError("Vectors must contain finite values.")
    norm = math.sqrt(sum(x * x for x in left) * sum(x * x for x in right))
    if norm == 0:
        return 0.0
    return max(
        -1.0, min(1.0, sum(a * b for a, b in zip(left, right, strict=True)) / norm)
    )


@dataclass
class RankedPassage:
    index: int
    similarity: float


def rank_passages(
    claim: str,
    passages: list[str],
    provider: EmbeddingProvider,
    top_k: int,
    min_similarity: float,
) -> list[RankedPassage]:
    if not passages:
        return []
    vectors = provider.encode([claim, *passages])
    if len(vectors) != len(passages) + 1:
        raise ValueError("Embedding provider returned the wrong number of vectors.")
    ranked = []
    for index, vector in enumerate(vectors[1:]):
        similarity = cosine_similarity(vectors[0], vector)
        # Ignore weak matches so unrelated passages cannot influence the verdict.
        if similarity >= min_similarity:
            ranked.append(RankedPassage(index, similarity))
    return sorted(ranked, key=lambda item: -item.similarity)[:top_k]
