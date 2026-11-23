from functools import lru_cache
from typing import Protocol

from app.core.errors import ProviderError
from app.core.settings import get_settings


class EmbeddingProvider(Protocol):
    def encode(self, texts: list[str]) -> list[list[float]]: ...


@lru_cache(maxsize=2)
def load_model(name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(name, device="cpu", trust_remote_code=False)


class LocalEmbeddings:
    def __init__(self, model_name: str):
        self.model_name = model_name

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Load once per process; embeddings are never persisted with reports."""
        if not texts:
            return []
        try:
            return (
                load_model(self.model_name)
                .encode(texts, batch_size=get_settings().embedding_batch_size)
                .tolist()
            )
        except Exception as exc:
            raise ProviderError("The local embedding model is unavailable.") from exc
