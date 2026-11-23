# Remediation pass 5 — working notes (parts 1–9)

Full narrative goes in `docs/remediation-final-report.md`; this is the
dev-time record of what was tried and measured, kept alongside the data it
was measured from.

## Part 1–2: new multi-fold contradiction corpus

`evaluation/remediation/data/contradiction-corpus.json`: 684 pairs (228 per
label), 3 balanced folds (76/label/fold). 600 mined fresh from the
2400-pair ANLI pool (only 1320 of 2400 previously consumed by pass2 +
Group 4), 84 hand-authored across the 14 stress categories in the
remediation instructions (same entity/different predicate, subtle
negation, date/number mismatch, causal-vs-correlational, partial
entailment, lexical-overlap traps, long-passage distraction, paraphrased
contradiction, entity-role reversal, ranking claims, temporally-compatible-
different-facts, similar named entities, implicit contradiction). Leakage
audit (`audit_corpus.py`): 0 exact overlaps, 0 near-duplicates, 0 internal
duplicates against 7,133 prior items scanned (Pass 2, old final, Group 4
Hyper holdout).

## Part 3: model comparison (`results/fold-analysis.json`)

| Model | Macro F1 (mean±std) | Latency (median ms) | Params (M) |
|---|---:|---:|---:|
| Current: DeBERTa-v3-large-mnli-fever-anli-ling-wanli | **0.768 ± 0.012** | 267.5 | 435.1 |
| Previous base: DeBERTa-v3-base-mnli-fever-anli | 0.624 ± 0.030 | 84.8 | 184.4 |
| Alternative: cross-encoder/nli-deberta-v3-small | 0.341 ± 0.022 | 45.6 | 141.9 |

The current model wins decisively and stably (lowest fold-to-fold
variance too) — no model change indicated. `facebook/bart-large-mnli`
(the originally intended third candidate) reproducibly crashed this
machine's CPU inference with SIGBUS on the first batch; substituted
`cross-encoder/nli-deberta-v3-small`, which is clearly weaker anyway.

## Part 2 + 6: threshold stability sweep

No single confidence threshold on the current model clears precision≥85%
/ recall≥65% / false-contradiction≤5% simultaneously with no fold
collapse — the closest is t≈0.90 (P=0.871, R=0.649 — recall just misses).
Full sweep in `results/fold-analysis.json` → `threshold_sweep`.

## Part 5: two-signal gating (confidence AND relevance corroboration)

Requiring predicted-contradict evidence to also clear a relevance-
corroboration floor materially improves precision/false-contradiction-rate
at a real but bounded recall cost. Best found: t=0.68, relevance floor
≈-1.5: **P=0.869 (min 0.852), R=0.671 (min 0.658), FCR=0.0504 (max
0.059)** — close to but not quite under the aspirational FCR≤5%, stable
across all 3 folds (no collapse). No swept combination clears all three
targets exactly; this is the best-balanced, most-stable point, honestly
reported as "close, not fully met" (see settings.py comment for the exact
adopted values: `min_contradiction_confidence=0.68`,
`contradiction_relevance_floor=-1.5`).

## Production change adopted

`api/app/services/pipeline.py` — `gate_stance` now applies a
contradiction-specific relevance floor (loosens the existing 0.0 floor to
-1.5 for contradiction stance only; support/neutral unchanged). Combined
with lowering `min_contradiction_confidence` 0.70→0.68.
`relevance_weight_and_directness` gained an optional `floor` parameter to
support this (default unchanged, backward compatible).

Diagnostic replay against the Group 4 Hyper holdout's 41 false abstentions
(diagnostic-only, not used to choose the value): only 2/41 had a genuine
raw-contradict passage in the newly-recovered relevance band — a modest,
not overstated, expected effect.

## Part 7: false-abstention taxonomy (diagnostic replay on Hyper holdout)

41 false abstentions classified by actual stored evidence fields:

| Cause | Count | % |
|---|---:|---:|
| Relevance score too low | 20 | 48.8% |
| NLI raw-neutral (genuine model miss, not a filter) | 12 | 29.3% |
| Claim-risk high-risk evidence minimum (0.65 vs single moderate source) | 4 | 9.8% |
| Claim-risk independent-source restriction (<2 independent sources) | 2 | 4.9% |
| Evidence minimum not met (standard risk) | 2 | 4.9% |
| Missing retrieval | 1 | 2.4% |

Most "relevance score too low" cases are SciFact-origin (dense scientific
abstracts scoring systematically negative on the general-purpose relevance
cross-encoder) — a domain-calibration issue, not a simple threshold bug;
most of the underlying passages were also raw-neutral, not real signal
being discarded. Claim-risk restrictions (independent-source count,
high-risk evidence minimum) are a deliberate Group-1 safety feature and
were NOT loosened this pass — they protect against confidently-wrong
medical/financial claims backed by a single source, which is exactly the
kind of caution this project has repeatedly chosen to keep.

## Part 9: coverage operating curve — not separately re-derived this pass

`minimum_evidence` (0.20 standard / 0.65 high-risk) was extensively
calibrated by Group 3 against its own coverage/selective-accuracy curve
and was NOT the dominant false-abstention cause found in part 7 above (only
2/41 cases, standard-risk). Given the time budget for this pass and that
the taxonomy pointed at the relevance floor (addressed above) rather than
the evidence-total threshold, a fresh coverage-vs-selective-accuracy curve
on new development data was not separately re-run. This is a disclosed
scope limitation, not a finding that coverage is solved — see the
confirmation holdout's own coverage number for the actual current state.
