import re
from typing import Protocol

from app.core.settings import Settings


class ClaimExtractor(Protocol):
    def extract(self, text: str) -> list[str]: ...


class SentenceClaimExtractor:
    def __init__(self, settings: Settings):
        self.settings = settings

    def extract(self, text: str) -> list[str]:
        """Propose sentences for human review; do not silently rewrite their meaning."""
        sentences = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
        selected = []
        for sentence in sentences:
            sentence = " ".join(sentence.split())
            if (
                self.settings.min_claim_chars <= len(sentence) <= 1000
                and not sentence.endswith("?")
                and sentence not in selected
            ):
                selected.append(sentence)
            if len(selected) >= self.settings.max_claims:
                break
        return selected
