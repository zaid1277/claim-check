import pytest

from app.services.retrieval import cosine_similarity, rank_passages


def test_cosine_geometry_and_zero_vectors():
    assert cosine_similarity([1, 0], [2, 0]) == 1
    assert cosine_similarity([1, 0], [0, 1]) == 0
    assert cosine_similarity([1, 0], [-1, 0]) == -1
    assert cosine_similarity([0, 0], [1, 0]) == 0
    with pytest.raises(ValueError):
        cosine_similarity([1], [1, 2])
    with pytest.raises(ValueError):
        cosine_similarity([float("nan")], [1])


def test_threshold_and_top_k():
    class FixedEmbeddings:
        def encode(self, texts):
            return [[1, 0], [0, 1], [1, 0], [0.8, 0.2]]

    ranked = rank_passages(
        "claim", ["irrelevant", "exact", "related"], FixedEmbeddings(), 1, 0.5
    )
    assert [item.index for item in ranked] == [1]
