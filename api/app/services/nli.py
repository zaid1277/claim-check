from functools import lru_cache
from typing import Protocol

from app.core.errors import ProviderError
from app.core.settings import get_settings
from app.schemas.investigation import Stance


class NLIProvider(Protocol):
    def classify(self, claim: str, passage: str) -> tuple[Stance, float]: ...


def normalize_hypothesis(claim: str) -> str:
    """Supply sentence punctuation for NLI without changing the stored claim."""
    text = claim.strip()
    # MNLI predictions can flip when a typed claim omits its final period.
    if text and not text.rstrip("\"'”’)]}").endswith((".", "!", "?", "…")):
        text += "."
    return text


@lru_cache(maxsize=2)
def load_nli(name: str):
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(name, trust_remote_code=False)
    model = AutoModelForSequenceClassification.from_pretrained(
        name, trust_remote_code=False
    )
    model.eval()
    return tokenizer, model


class LocalNLI:
    def __init__(self, model_name: str, min_confidence: float):
        self.model_name = model_name
        self.min_confidence = min_confidence

    def classify(self, claim: str, passage: str) -> tuple[Stance, float]:
        """Use the passage as premise and the claim as hypothesis."""
        try:
            import torch

            tokenizer, model = load_nli(self.model_name)
            inputs = tokenizer(
                passage,
                normalize_hypothesis(claim),
                return_tensors="pt",
                truncation="only_first",
                max_length=get_settings().nli_max_tokens,
            )
            with torch.inference_mode():
                probabilities = model(**inputs).logits[0].softmax(dim=-1)
            index = int(probabilities.argmax())
            confidence = float(probabilities[index])
            label = model.config.id2label[index].lower()
            return interpret_label(label, confidence, self.min_confidence)
        except Exception as exc:
            raise ProviderError("The local NLI model is unavailable.") from exc


def interpret_label(
    label: str, confidence: float, threshold: float
) -> tuple[Stance, float]:
    labels: dict[str, Stance] = {
        "entailment": "support",
        "contradiction": "contradict",
        "neutral": "neutral",
    }
    if label not in labels:
        raise ValueError("The model must expose explicit NLI labels.")
    # Uncertain classifications must not add directional evidence.
    return (labels[label] if confidence >= threshold else "neutral", confidence)
