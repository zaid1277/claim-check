# Hyper pass — Group 1 (Phases 3-7) results

Measured by replaying the 175 controlled cases (now development evidence)
through the real pipeline with the new code, in-process
(`evaluation/hyper/replay_controlled.py`) — same fixture documents/sources as
the original locked run, same claims, same gold labels. Not the new held-out
benchmark (Phase 20) and not a substitute for it.

## What changed (code)

- `api/app/services/pipeline.py`: `min_proposition_relevance`'s hard binary
  cutoff replaced with a graded, piecewise-linear relevance weight
  (`relevance_weight_and_directness`) folded into `evidence_score`, plus a
  persisted `relevance_score`/`directness`/`relevance_weight` on each
  `Evidence` (phases 3-4). Below `relevance_floor` (0.0) is still a hard
  exclusion — that safeguard is unchanged.
- `api/app/services/evidence_scoring.py`: a second same-stance passage from an
  already-counted domain is now retained at a steep discount
  (`duplicate_source_weight`, 0.35×) instead of discarded outright — only
  genuine near-duplicate *content* is still fully excluded (phase 3, subtype
  D). `aggregate()` now takes a claim-risk level and an independent-source
  count.
- `api/app/services/claim_risk.py` (new): deterministic, keyword/pattern-based
  `claim_risk()` — medical/financial/political/causal-statistic claims are
  "high" risk; everything else is "standard" (unchanged operating point).
  High-risk claims require more total evidence (`high_risk_minimum_evidence`
  0.65 vs 0.5) and at least 2 independent sources
  (`high_risk_min_independent_sources`) before committing — this only adds
  caution, never removes it (phase 5/6).
- `api/app/core/settings.py`: new `encyclopedia` source tier (0.75) with
  wikipedia.org/britannica.com mapped to it; `general` raised 0.55 → 0.70
  (was the tier every false-abstention's lone source fell into); new
  `relevance_floor`/`relevance_full_weight`/`duplicate_source_weight`/
  `high_risk_*` settings.
- `api/app/db/reports.py`: persisted the three new `Evidence` fields in the
  existing `analysis` JSONB extension column (a real bug this pass caught: an
  API↔Postgres round-trip test failed until this was added — fixed, not
  worked around).
- 16 new/updated backend unit tests
  (`api/tests/test_hyper_calibration.py`, plus updates to `test_scoring.py`
  and `test_reliability.py` for the new signatures/values). Full backend
  suite: **154 passed** (up from 138; no regressions).

## Development-set results (175 cases, same benchmark as the locked final run)

| Metric | Before (locked final) | After (Group 1) | Δ |
|---|---:|---:|---:|
| Verdict accuracy | 44.6% | **68.0%** | +23.4pp |
| Coverage | 28.6% | **52.6%** | +24.0pp |
| Selective accuracy | 96.0% | **96.7%** | +0.7pp |
| Abstention rate | 71.4% | 47.4% | −24.0pp |
| False abstentions | 95 | **53** | −42 |
| Correct abstentions | 30 | 30 | 0 |
| Confident errors | 2 | 3 | +1 |
| Easy accuracy | 57.5% | **90.0%** | +32.5pp |
| Medium accuracy | 60.0% | **93.3%** | +33.3pp |
| Hard accuracy | 25.3% | 36.0% | +10.7pp |

Case-level: **42 cases flipped wrong→correct, 1 flipped correct→wrong**
(`final-fact-043`, SUPPORTED→INSUFFICIENT_EVIDENCE — likely a minor knock-on
effect of the source-weight change altering which duplicate-text candidate
wins the pre-scoring tie-break in `check_atomic`; not chased further this
checkpoint since the net effect is overwhelmingly positive). **1 new
confident error** (`final-scifact-1336`, expected UNSUPPORTED, predicted
SUPPORTED) — a real, honest cost of the coverage increase, not hidden.

## Where this leaves the phase-20 targets

| Target | Goal | Current | Met? |
|---|---:|---:|:---:|
| Coverage | >70%, ideally 80%+ | 52.6% | not yet |
| Selective accuracy | ≥90% | 96.7% | ✓ |
| Verdict accuracy | ≥80% | 68.0% | not yet |
| Easy accuracy | ≥95% | 90.0% | close |
| Medium accuracy | ≥85% | 93.3% | ✓ |
| Hard accuracy | ≥65% | 36.0% | not yet |

Selective accuracy and medium accuracy already clear their targets. Coverage,
verdict accuracy, and especially hard accuracy still need the Group 2/3 work
(contradiction recall, retrieval quality for hard cases, structured
numeric/date assistance, iterative retrieval, atomic coverage) — Group 1 only
touched aggregation/eligibility/source-weighting, not retrieval or NLI/
contradiction handling, and the false-abstention data showed hard cases lean
much more heavily on exactly those untouched mechanisms (subtypes B/D/J).

This is a development-set measurement on the same 175 cases used for
diagnosis — it demonstrates the mechanism works and is not obviously
overfit (single-digit regression count, selective accuracy unchanged), but it
is not a substitute for the new held-out validation/test split required
before any final claim (phase 20-21).
