"""A passage relevance score, not a truth probability or NLI stance."""

import math
from functools import lru_cache

from app.core.errors import ProviderError


@lru_cache(maxsize=1)
def load_relevance(name: str):
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(name, trust_remote_code=False)
    # Float32 BERT inference crashed or returned NaNs on the evaluated macOS CPU.
    # Float64/eager inference was finite and repeatable; report its memory cost.
    model = AutoModelForSequenceClassification.from_pretrained(
        name, trust_remote_code=False, attn_implementation="eager"
    ).double()
    model.eval()
    return tokenizer, model


@lru_cache(maxsize=1024)
def relevance_score(claim: str, passage: str, model_name: str) -> float:
    try:
        import torch

        tokenizer, model = load_relevance(model_name)
        inputs = tokenizer(
            claim, passage, return_tensors="pt", truncation=True, max_length=512
        )
        with torch.inference_mode():
            score = float(model(**inputs).logits[0, 0])
        if not math.isfinite(score):
            raise ValueError("Non-finite relevance score")
        return score
    except Exception as exc:
        raise ProviderError(
            "The local proposition relevance model is unavailable."
        ) from exc
