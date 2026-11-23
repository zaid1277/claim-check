# Phase 1: quantitative error-budget model

Base data: 400 combined cases from the two prior independent holdouts
(diagnostic use only, per Rule 1), 316 correct (79.0%), 84 errors.

## Naive (surface) taxonomy attribution

From the accuracy-max pass's A-S classification of the 84 errors:

| Category | Layer (surface reading) | Count | % of errors |
|---|---|---:|---:|
| Q (false abstention) | aggregation/coverage threshold | 20 | 23.8% |
| D (excluded pre-NLI) | retrieval/relevance-gating | 16 | 19.0% |
| J (neutral misclassification) | NLI/verifier | 15 | 17.9% |
| P (aggregation mistake) | aggregation | 10 | 11.9% |
| M (entity mismatch, heuristic) | entity resolution | 9 | 10.7% |
| K (temporal reasoning) | temporal | 7 | 8.3% |
| H (NLI contradiction miss) | NLI/verifier | 2 | 2.4% |
| S (genuinely ambiguous) | ambiguity (unfixable) | 2 | 2.4% |
| B (source not found) | retrieval | 1 | 1.2% |
| N, O (source quality/independence) | source conflict | 2 | 2.4% |
| A, C, E, F, G, I, L, R | (retrieval-query, extraction, reranking, decomposition, NLI-support-miss, false-contradiction, numeric, compound-policy) | 0 | 0% |

Read naively, this makes gating/aggregation (Q+D+P = 46/84 = 54.8%) look
like the dominant lever.

## Corrected attribution (direct oracle experiment, already run and validated)

The naive reading is **wrong**, proven directly: re-running the real,
unmodified `assess()` aggregation function with every pre-NLI gate
removed (relevance floor, confidence threshold, temporal exclusion all
bypassed, every evidence item's stance forced to its raw NLI label) on
these same 400 cases:

| | Accuracy | Correct |
|---|---:|---:|
| Actual production (all gates active) | 79.00% | 316/400 |
| Oracle: raw NLI + zero gating | 80.25% | 321/400 |

**Gating/aggregation removal recovers only 5 of the 84 errors (6.0%).**
The gating+aggregation system is already operating at **98.4% efficiency**
relative to the ceiling the current raw verifier allows
(0.7900 / 0.8025 = 0.9844). This means categories D, J, and most of Q are
**not** gating failures in the actionable sense — they are cases where the
raw NLI model itself produced no usable, correct-direction signal on the
retained evidence. Manual inspection of category M ("entity mismatch")
further found most of those cases are SciFact scientific abstracts with
no capitalized terms overlapping the claim at all -- a relevance-model
domain-calibration symptom of the same underlying issue, not genuine
person/place/company confusion.

## Corrected layer attribution

| Layer | Errors attributable | % of total errors |
|---|---:|---:|
| **Verifier (NLI stance recognition)** | ~79 (84 total − 5 gating-recoverable) | **~94%** |
| Aggregation math (genuine two-sided-evidence cases, P) | 10 | 11.9% (overlaps partially with verifier-caused totals above) |
| Temporal reasoning (K) | 7 | 8.3% |
| Retrieval (B, true source-not-found) | 1 | 1.2% |
| Source conflict (N, O) | 2 | 2.4% |
| Genuinely ambiguous / bad gold (S) | 2 | 2.4% (not fixable by any architecture) |
| Retrieval query/extraction/reranking/decomposition/numeric (A, C, E, F, L, R) | 0 | 0% (not measurable as a failure source in this controlled-evidence dataset -- see caveat below) |

**Caveat:** these 400 cases are controlled/fixture investigations where
gold evidence is supplied directly -- retrieval succeeds by construction.
Categories A/C/E (search, extraction, reranking) genuinely cannot show up
as failures in this dataset regardless of their real-world rate. This is
exactly why Phase 2 (a live-search retrieval-oracle test) is necessary
before concluding retrieval is not a bottleneck for real usage.

## Multiplicative ceiling model

Treating the pipeline as `verifier_success × aggregation_efficiency` for
a fixed evidence pool (valid for this controlled dataset where retrieval
is not in question):

```
observed = verifier_raw_success x aggregation_efficiency
0.7900   = 0.8025             x 0.9844
```

Aggregation efficiency is already near its ceiling (98.4%) and cannot
realistically be pushed much past ~99% (the 2 "genuinely ambiguous"
cases and some fraction of the 7 temporal-reasoning cases will resist any
aggregation formula). **For 95% end-to-end accuracy at ~99% aggregation
efficiency, the underlying verifier's raw success rate must rise from
~80.25% to ~96.0%** -- a required gain of **+15.75 percentage points**.

For context: the one fine-tuning experiment already run (nli-upgrade
pass) produced a clean +1.95pp macro-F1 gain on held-out data. **Closing
a 15.75pp gap is roughly 8x larger than what one modest LoRA fine-tune
delivered.** This does not mean it is impossible -- it means it requires a
materially more capable verifier, not another round of threshold or
LoRA-scale tuning. This is the precise, quantified answer to "prove what
must improve": **the verifier layer, and by a wide margin.**
