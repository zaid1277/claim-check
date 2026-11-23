from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, PostgresDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Resolve from this file so starting the API from another directory still works.
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    allow_runtime_provider_keys: bool = False

    search_provider: Literal["tavily", "brave", "mock"] | None = None
    tavily_api_key: SecretStr | None = None
    brave_search_api_key: SecretStr | None = None
    search_results: int = Field(default=5, ge=1, le=20)
    provider_mode: Literal["fixture", "live"] = "fixture"

    embedding_batch_size: int = Field(default=16, ge=1, le=64)
    nli_max_tokens: int = Field(default=512, ge=128, le=512)
    min_claim_chars: int = Field(default=20, ge=3, le=1000)

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    min_similarity: float = Field(default=0.35, ge=0, le=1)
    top_k: int = Field(default=10, ge=1, le=30)
    passage_words: int = Field(default=100, ge=20, le=200)
    # Raised from 10 (hyper pass, phase 14): validation found a genuinely
    # relevant source dropped purely because raw search-result order put it
    # after 10 lower-value results -- before any similarity ranking ever saw
    # it. 15 recovered that case; 20 gave no further benefit there.
    max_sources: int = Field(default=15, ge=1, le=25)
    # Cap candidate passages per registrable domain before similarity ranking
    # (hyper pass, phase 13); 0/None disables the cap.
    max_candidates_per_domain: int = Field(default=3, ge=0, le=50)
    # Hyper pass, phase 15: one deterministic, targeted follow-up search when
    # the first pass leaves an atom without independent evidence.
    allow_follow_up_search: bool = True
    max_follow_up_queries: int = Field(default=1, ge=0, le=2)

    # Changed from MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli (hyper pass,
    # group 3, phase 1): benchmarked 5 practical local-CPU candidates on the
    # 120-pair validation split (never the future Hyper holdout). This
    # larger, same-lineage model trained on more/broader NLI data won on
    # every axis simultaneously -- macro F1 0.759 vs 0.594, contradiction
    # precision 83.8% vs 72.7%, recall 77.5% vs 60.0%, false contradiction
    # rate 7.5% vs 11.3% -- and recovered 7/27 of the historical "confidently
    # wrong direction" misses that no amount of threshold tuning could fix
    # (0/27 recovered by the old model at any gate). Real cost: ~3x latency
    # (277ms vs 88ms median per pair) and a larger memory footprint (~2GB
    # peak RSS vs the old model's ~700MB-1GB) -- both measured, not
    # estimated, and judged worth it given the magnitude of the gain. Two
    # smaller candidates (cross-encoder/nli-deberta-v3-small,
    # typeform/distilbert-base-uncased-mnli) were also benchmarked and were
    # decisively weaker on every axis (macro F1 0.35 and 0.30) -- rejected.
    # facebook/bart-large-mnli crashed with a low-level bus error twice in
    # this environment (likely a memory constraint) and was dropped rather
    # than chased further, given this candidate already won decisively.
    nli_model: str = "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli"
    proposition_model: str = "cross-encoder/ms-marco-MiniLM-L6-v2"
    min_proposition_relevance: float = 2.0
    # Below this raw cross-encoder score, a passage is treated as irrelevant and
    # excluded outright. Between the floor and min_proposition_relevance it now
    # contributes at a steep discount rather than being discarded (hyper pass,
    # phase 3/4: graded relevance replaces a hard cliff). See relevance_weight().
    relevance_floor: float = 0.0
    # Remediation pass 5, parts 5/8: contradiction evidence gets its own,
    # more permissive floor for the retain-vs-exclude decision (the
    # continuous weight curve itself is unchanged). A NEW, independent
    # 684-pair, 3-fold-validated corpus (evaluation/remediation/data/
    # contradiction-corpus.json -- never the Group 4 Hyper holdout, per
    # part 16) found the general 0.0 floor was demoting genuine,
    # correctly-flagged contradictions with mildly negative relevance
    # scores to neutral for no false-contradiction-rate benefit: loosening
    # it to -1.5 for contradiction specifically recovered recall (fold
    # mean 0.645->0.671) AND improved precision (0.865->0.869) and false-
    # contradiction rate (0.0504, flat) simultaneously, stable across all
    # 3 folds (see evaluation/remediation/results/fold-analysis.json).
    # Support/neutral evidence still uses the unchanged general floor.
    contradiction_relevance_floor: float = -1.5
    # At/above this raw score, relevance no longer discounts evidence_score.
    relevance_full_weight: float = 4.0
    min_nli_confidence: float = Field(default=0.65, ge=0, le=1)
    # Lowered from 0.85 (hyper pass, phase 6-7): a validation-only
    # precision-recall sweep of the new model's contradiction confidence
    # found 0.70 is the lowest threshold that still clears 88% precision
    # (88.2% measured), at 75.0% recall -- both group-3 targets met
    # simultaneously. No threshold reached 92% precision without recall
    # collapsing, so 88% was the achievable, defensible Pareto point, not
    # the aspirational one. Also found real overconfidence at this
    # threshold's high end (ECE 0.154 for the contradict class; predictions
    # at ~99% raw confidence are only ~87% actually correct) -- a remaining
    # limitation, not something this threshold change fixes.
    #
    # Remediation pass 5, part 1-2: that 88.2%/75.0% pair was measured only
    # on Group 3's own development validation split. On a genuinely new,
    # independent Hyper holdout it did not hold (76.1%/58.1%, false-
    # contradiction rate 9.4%) -- a real generalization failure, not a
    # measurement fluke (Group 4 report, hyper-final-reliability-report.md
    # section 10/34). Lowered slightly further, from 0.70 to 0.68, and
    # paired with contradiction_relevance_floor above: multi-fold
    # cross-validation on the new corpus found NO single-threshold
    # configuration clears precision>=85%/recall>=65%/false-contradiction
    # <=5% simultaneously (the same kind of Pareto limit Group 3 already
    # found on its own data, now confirmed independently) -- 0.68 combined
    # with the new relevance floor is the most stable point found (mean
    # precision 0.869, recall 0.671, false-contradiction rate 0.0504,
    # low fold-to-fold variance, no fold collapse). This is reported
    # honestly as "close, not fully met" rather than force-fit further.
    min_contradiction_confidence: float = Field(default=0.68, ge=0, le=1)
    max_atomic_claims: int = Field(default=4, ge=1, le=5)
    duplicate_similarity: float = Field(default=0.9, ge=0, le=1)
    # A second same-stance passage from an already-used domain (but not
    # near-duplicate content) is no longer discarded outright; it is retained
    # at this discount (hyper pass, phase 3: independence dedup was a hard
    # cliff that cost real evidence — see false-abstention subtype D).
    duplicate_source_weight: float = Field(default=0.35, ge=0, le=1)
    current_evidence_days: int = Field(default=365, ge=1)
    # Lowered from 0.5 (hyper pass, group 3, phase 14): a validation sweep of
    # this exact threshold (0.10/0.15/0.20/0.30/0.40/0.50/0.65) on the 175-
    # case development replay found 0.15-0.20 is a plateau -- same accuracy/
    # coverage/selective-accuracy as 0.15, but one fewer confident error than
    # 0.10 (5 vs 6, at the group-3 target ceiling). Below 0.10 the false-
    # abstention count stopped improving while confident errors kept rising,
    # so this is not "as low as possible" -- it's the validated plateau
    # point. High-risk claims are unaffected (they use the separate, still-
    # cautious high_risk_minimum_evidence below).
    minimum_evidence: float = Field(default=0.20, gt=0)
    dominance_ratio: float = Field(default=2.0, gt=1)
    # Higher-risk claims (medical/financial/statistical/political -- see
    # claim_risk.py) keep the original, more cautious operating point instead
    # of benefiting from the standard-claim recalibration below.
    high_risk_minimum_evidence: float = Field(default=0.65, gt=0)
    high_risk_dominance_ratio: float = Field(default=2.5, gt=1)
    high_risk_min_independent_sources: int = Field(default=2, ge=1)
    # Hyper pass, group 3, phase 11/13: lets a clearly more authoritative
    # source resolve a MIXED_EVIDENCE tie, but only when the other side isn't
    # itself authoritative (max_opposing_weight) and isn't well-corroborated
    # by several independent sources (max_opposing_sources) -- so it can
    # resolve "10 copied blog pages vs. 1 SEC filing" without letting "1
    # official statement" simply out-rank "5 independent investigative
    # sources". See evidence_scoring._authority_tiebreak.
    authority_tiebreak_enabled: bool = True
    authority_tiebreak_min_weight: float = Field(default=0.90, ge=0, le=1)
    authority_tiebreak_max_opposing_weight: float = Field(default=0.75, ge=0, le=1)
    authority_tiebreak_max_opposing_sources: int = Field(default=2, ge=1)
    max_passages: int = Field(default=100, ge=1, le=300)
    source_weights: dict[str, float] = {
        "research": 1.0,
        "official": 0.95,
        "institution": 0.90,
        "reporting": 0.75,
        "encyclopedia": 0.75,
        "general": 0.70,
        "unknown": 0.30,
    }
    source_domains: dict[str, str] = {
        "nature.com": "research",
        "science.org": "research",
        "reuters.com": "reporting",
        "apnews.com": "reporting",
        "bbc.com": "reporting",
        "wikipedia.org": "encyclopedia",
        "britannica.com": "encyclopedia",
        "blogspot.com": "unknown",
        "substack.com": "unknown",
    }

    max_claims: int = Field(default=5, ge=1, le=5)

    max_image_bytes: int = 5_000_000
    max_image_pixels: int = 12_000_000

    requests_per_minute: int = Field(default=30, ge=1, le=300)

    @model_validator(mode="after")
    def valid_source_heuristics(self):
        if self.provider_mode == "live" and self.search_provider == "mock":
            raise ValueError("The mock provider is only available in fixture mode.")
        required = {
            "research",
            "official",
            "institution",
            "reporting",
            "encyclopedia",
            "general",
            "unknown",
        }
        if set(self.source_weights) != required:
            raise ValueError("Configure all seven source-weight categories.")
        if any(not 0 <= weight <= 1 for weight in self.source_weights.values()):
            raise ValueError("Source weights must be between zero and one.")
        if any(kind not in required for kind in self.source_domains.values()):
            raise ValueError("Source domains must use configured weight categories.")
        return self

    database_url: PostgresDsn | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
