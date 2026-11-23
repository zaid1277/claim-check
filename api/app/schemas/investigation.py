from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

Verdict = Literal["SUPPORTED", "UNSUPPORTED", "MIXED_EVIDENCE", "INSUFFICIENT_EVIDENCE"]
Stance = Literal["support", "contradict", "neutral"]


class ClaimInput(BaseModel):
    claim: str = Field(min_length=3, max_length=1000)

    @field_validator("claim")
    @classmethod
    def clean_claim(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 3:
            raise ValueError("Enter a claim of at least three characters.")
        return value


class Evidence(BaseModel):
    title: str
    url: str
    domain: str
    published_at: str | None = None
    passage: str
    similarity: float = Field(ge=0, le=1)
    stance: Stance
    stance_confidence: float = Field(ge=0, le=1)
    source_type: str = "general"
    source_weight: float = Field(default=0.55, ge=0, le=1)
    evidence_score: float = Field(ge=0, le=1)
    raw_stance: Stance | None = None
    exclusion_reason: str | None = None
    independence_group: str | None = None
    counted: bool = True
    atomic_claim: str | None = None
    relevance_score: float | None = None
    directness: Literal["direct", "related", "contextual", "irrelevant"] | None = None
    relevance_weight: float | None = Field(default=None, ge=0, le=1)
    structured_signal: Literal["numeric", "temporal", "location", "negation"] | None = (
        None
    )


class AtomicAssessment(BaseModel):
    claim: str
    verdict: Verdict
    support_total: float
    contradict_total: float
    evidence_indices: list[int] = Field(default_factory=list)


class Assessment(BaseModel):
    claim: str
    verdict: Verdict
    explanation: str
    support_total: float = 0
    contradict_total: float = 0
    evidence: list[Evidence] = Field(default_factory=list)
    atomic_claims: list[AtomicAssessment] = Field(default_factory=list)
    # Hyper pass, group 3, phase 10: internal-only for now (not surfaced in
    # the UI -- phase 9's compound-probe experiment found the existing
    # verdict policy already correct on every curated case, so this isn't
    # used to change the decision, only to make partial verification
    # legible for debugging/future use).
    verified_atom_fraction: float | None = None
    contradicted_atom_fraction: float | None = None


class Investigation(BaseModel):
    id: UUID
    created_at: datetime
    status: Literal["complete"] = "complete"
    mode: str
    assessments: list[Assessment]
    share_slug: str | None = None
    input_type: str = "claim"
    source_url: str | None = None
    raw_text: str = Field(default="", exclude=True)
    model_metadata: dict[str, str] = Field(default_factory=dict)
