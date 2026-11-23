# Claim Check — 95% Accuracy Challenge: Development-Only Findings

**Per the stop condition: no new development corpus (Phase 24) and no
final 500-case holdout (Phase 25) were built.** This pass answers the
required question first — does the architecture, or any tested
alternative, plausibly reach 95% — using real experiments, then stops for
a decision.

## 1. Current architecture ceiling

From the accuracy-max pass (400 combined cases from the two prior
independent holdouts, diagnostic use only): **79.0% actual, ~80.25%
theoretical ceiling** even with every pre-NLI gate removed (full
aggregation-oracle simulation). This is the number every subsequent
section is measured against.

## 2. Retrieval oracle — blocked, not resolved

A genuine, new live-search retrieval-oracle test was built (30 fresh,
independently-verified claims, real Tavily search + extraction + ranking,
checking whether correct-direction evidence appears in the candidate pool
at all, not just after downstream gating). **It hit Tavily's usage quota
after 2 of 30 claims.** Both completed claims found correct evidence at
rank 1 of a wide candidate pool — consistent with, but nowhere near
sufficient to prove, "retrieval is not the bottleneck." **This is reported
honestly as an unresolved measurement, not papered over with n=2 treated
as n=30.** Retrieval oracle ceiling: **not established this pass.**

## 3. Failure taxonomy (recap, already computed and validated)

Of 84 errors across 400 cases: after correcting the naive surface reading
with a direct oracle experiment, **~94% of errors are attributable to the
verifier layer** (NLI stance recognition failing to produce usable,
correct-direction signal on retained evidence), **~6% to gating/
aggregation** (already 98.4% efficient relative to what the verifier's
raw output allows), ~8% temporal reasoning, ~2% genuinely ambiguous/bad
gold, ~1% true retrieval failure. Full detail:
`evaluation/accuracy95/results/error-budget.md`.

## 4. Quantitative error-budget model (Phase 1)

```
observed_accuracy = verifier_raw_success x aggregation_efficiency
0.7900             = 0.8025             x 0.9844
```

Aggregation efficiency is already near its practical ceiling (~98-99%).
**For 95% end-to-end accuracy, the verifier's raw success rate must rise
from ~80.25% to ~96.0% — a required gain of +15.75 percentage points.**
This is the single number that governs everything else in this report.

## 5. Query improvements (Phase 3) — not attempted

Deferred: with retrieval oracle status unresolved (§2) and the error
budget showing verifier capability as the overwhelming lever (§4), query
engineering work was not prioritized this pass. This is a real, disclosed
gap, not a finding that it's unnecessary.

## 6. Reranker comparison (Phase 5) — not attempted

Same reasoning as §5: no evidence this pass points at reranking as a
measurable bottleneck in the controlled-evidence dataset (0/84 errors
attributed to category E), and the live-search side needed to test it
properly was blocked (§2).

## 7. Verifier architectures compared

| Option | Tested? | Result |
|---|---|---|
| A. existing NLI-only verifier | Yes (baseline) | Macro F1 81.44%, established ceiling ~80.25% |
| B. stronger fine-tuned NLI | Yes (prior pass) | Macro F1 83.39% (+1.95pp) — real but far short of +15.75pp needed |
| C. two-model NLI consensus | Tested (prior pass) | Weaker second model recovered only 14.9% of primary's misses; not adopted |
| D. NLI + evidence-grounded reasoning model | **New this pass** | See §8 |
| E. evidence-grounded reasoning model with NLI validation | Not attempted | Would only be worth building if D showed D alone was competitive; it was not (§8) |

## 8. Strong-model comparison / evidence-grounded reasoning model (Phases 6-8)

**Qwen2.5-1.5B-Instruct**, run locally (CPU, bfloat16, no API cost, no
GPU) as the "evidence-grounded reasoning" verifier Phase 7 describes:
given ONLY claim + evidence, asked to output structured JSON
(`{"stance", "confidence", "reasoning"}`), explicitly instructed to reason
only from supplied evidence, not general knowledge. Evaluated on a
stratified 120-pair subset (40/label) of the nli-upgrade validation split
(the full 380 would take over an hour at measured per-pair latency; a
120-pair subset is disclosed, not silently substituted for the full set).

**Result: Macro F1 55.35% — a 26.1-point REGRESSION from the current NLI
model's 81.44% on comparable data.** Zero JSON parse failures (the model
follows the output-format instruction reliably), but the actual reasoning
quality is substantially worse:

| Label | Precision | Recall | F1 |
|---|---:|---:|---:|
| Support | 53.5% | 95.0% | 68.5% |
| Neutral | 37.0% | 25.0% | 29.9% |
| Contradict | 95.5% | 52.5% | 67.7% |

Predicted-label distribution (71 support / 27 neutral / 22 contradict vs.
40/40/40 expected) shows a clear, systematic failure mode: **the model
over-commits to "support" at high stated confidence (1.0) on evidence
that is merely topically related, not actually entailing** — e.g.
confidently calling "David Beckham played football in Canterbury, England"
support for a claim it doesn't actually establish. This is the well-known
weak point of small general-purpose instruction models on strict
entailment tasks: they're good at surface relevance, poor at the precise
logical distinction NLI requires. Latency: median 12.93s/pair (**~34x
slower** than the current NLI model's ~380ms).

**This directly answers Phases 6-9: for the one "evidence-grounded
reasoning model" option actually testable in this environment (free,
local, no GPU/API), the answer is clearly negative — it is a substantial
regression, not an improvement, and dramatically slower.**

## 9. Hybrid verifier results (Phase 9-10) — not attempted

Given §8's decisive negative result for the one locally-testable
reasoning-model candidate, building a hybrid escalation pipeline around
it (NLI + LLM consensus, disagreement handling) was not attempted — there
is no signal yet that the LLM component would contribute positively to
such a hybrid, and building the escalation machinery around a
demonstrated-weaker component would not be a responsible use of the
remaining time.

## 10. Scientific results

Not separately re-measured against the LLM verifier this pass (the
120-pair evaluation subset draws from the general nli-upgrade validation
pool, not scientific-only). The existing scientific-subset findings stand
unchanged: current NLI 61.97% F1, LoRA-tuned base 66.19% F1 (prior pass).

## 11. Entity reasoning (Phase 12) — not attempted

No new experiment. The accuracy-max pass's "entity mismatch" category
(9/84 errors) was already found, on inspection, to mostly reflect a
relevance-model domain-calibration symptom (SciFact abstracts with no
capitalized terms matching the claim) rather than genuine person/place/
company confusion — not re-litigated this pass.

## 12. Temporal reasoning (Phase 13) — not attempted

No new experiment. Existing measurement: 7/84 errors (8.3%) attributed to
temporal-reasoning failures in the error taxonomy — a real but secondary
contributor next to the verifier-capability gap.

## 13. Numerical reasoning (Phase 14) — not attempted

No new experiment. 0/84 errors were attributed to numeric-reasoning
failure in the controlled-evidence dataset (category L) — not measurable
as a bottleneck in the data available.

## 14. Compound claim results (Phase 15) — not attempted

0/84 errors attributed to decomposition/compound-claim-policy failure
(categories F, R) in the existing taxonomy — no experiment run this pass.

## 15. Learned aggregation results (Phase 19) — not attempted

Superseded by §4: aggregation is already measured at ~98.4% efficiency
relative to the verifier's raw ceiling. A learned aggregator could only
close that remaining ~1.6pp gap at best — far short of the +15.75pp
needed overall, so it was not prioritized this pass.

## 16. Hard-case escalation results (Phase 20) — not attempted

No escalation tier was built. With the one alternative verifier tested
(§8) performing substantially worse than the baseline, there is currently
nothing better to escalate hard cases *to*.

## 17. 5-fold results

Carried over from the nli-upgrade pass (the fine-tuned candidate, option
B in §7): macro F1 mean 82.78% (current, clean, never-trained-on-pool) vs
88.31% (candidate, train-data-leaked, not a trustworthy absolute number —
see that report's §12 caveat). No new 5-fold work this pass; the new
LLM-verifier experiment (§8) was not cross-validated given its clearly
negative single-split result made further validation rounds low-value.

## 18. Overall validation accuracy

| | Accuracy | Macro F1 |
|---|---:|---:|
| Current NLI (held-out validation, 380 pairs) | 80.79% | 81.44% |
| LoRA-tuned base NLI (same, prior pass) | 83.16% | 83.39% |
| LLM evidence-grounded verifier (120-pair subset) | 57.50% (of parsed) | **55.35%** |

## 19. Easy/medium/hard

Not re-measured end-to-end this pass (no new development corpus or
pipeline replay was run with the LLM verifier, given its poor pair-level
result made an expensive full pipeline integration test low-value before
reporting back). Existing figures (176-case dev pipeline replay, prior
passes): current 76.0% (easy 90%/medium 93.3%/hard 54.7%), LoRA candidate
76.6% (easy 95%/medium 96.7%/hard 50.7%).

## 20. Coverage

Not re-measured this pass for either new candidate (no full pipeline
integration run performed for the LLM verifier).

## 21. Selective accuracy

Same as §20 — not re-measured this pass.

## 22. Contradiction P/R

| | Precision | Recall |
|---|---:|---:|
| Current NLI | 93.7% | 80.9% |
| LoRA-tuned base (calibrated, t=0.65) | 91.0% | 82.7% |
| LLM verifier | 95.5% | 52.5% |

The LLM verifier's contradiction precision looks strong in isolation, but
its recall (52.5%) is the weakest of any candidate tested across this
whole project — it misses roughly half of all true contradictions,
consistent with its general over-eagerness toward "support."

## 23. Estimated final ceiling

**No experiment run in this pass (or the two prior passes) has moved the
estimated ceiling meaningfully above ~80-83%.** The required verifier
raw-success rate for 95% (§4) is ~96%. Nothing tested — a modest LoRA
fine-tune (+1.95pp), a locally-runnable small LLM reasoning verifier
(-26.1pp) — comes remotely close to that gap. Retrieval-oracle ceiling
remains unmeasured (§2) but even a perfect retrieval layer cannot close a
verifier-layer gap of this size, since the controlled-evidence dataset
(where retrieval is not in question at all) already shows the same ~80%
ceiling.

**Estimated total ceiling with resources available in this environment:
still ~80-83%,** not materially different from the accuracy-max pass's
original estimate.

## 24. Latency

| | Median | 
|---|---:|
| Current NLI | 382ms |
| LoRA-tuned base NLI | 132ms |
| LLM evidence-grounded verifier | 12,930ms (~34x current) |

## 25. Resource requirements

- Current/LoRA-base NLI: runs comfortably within this environment's 8GB
  RAM, CPU-only, no special hardware.
- LLM verifier (Qwen2.5-1.5B-Instruct, bfloat16): loads and runs within
  the same 8GB RAM (peak ~1.3GB for the model alone), but at ~34x the
  latency — a genuine deployment cost even setting aside the accuracy
  regression.
- Nothing in this pass required, or was run on, GPU/Colab/Kaggle/paid API
  infrastructure. No paid costs were incurred, per the explicit
  constraint.

## 26. Exact recommended architecture

**Keep the current architecture (NLI classifier + the existing gating/
aggregation pipeline) unchanged.** Neither tested alternative (fine-tuned
base-model NLI, small local LLM reasoning verifier) clears a bar anywhere
near what 95% requires, and the LLM verifier specifically performed worse
than the status quo by a wide, unambiguous margin. **No production code
was changed this pass.**

---

## Deliverable summary table (as requested)

| Metric | Current | Best New Architecture (tested) |
|---|---:|---:|
| Overall accuracy (held-out NLI validation) | 80.79% | 83.16% (LoRA base) / 57.50% (LLM verifier) |
| Coverage | not re-measured this pass | not re-measured this pass |
| Selective accuracy | not re-measured this pass | not re-measured this pass |
| Easy accuracy (175-case dev replay) | 90.0% | 95.0% (LoRA base) |
| Medium accuracy | 93.3% | 96.7% (LoRA base) |
| Hard accuracy | 54.7% | 50.7% (LoRA base, regressed) |
| Scientific accuracy (F1) | 61.97% | 66.19% (LoRA base) |
| Contradiction precision | 93.7% | 91.0% (LoRA, calibrated) / 95.5% (LLM) |
| Contradiction recall | 80.9% | 82.7% (LoRA, calibrated) / **52.5%** (LLM) |
| False contradiction rate | 2.22% | 3.33% (LoRA, calibrated) / n/a (LLM) |
| Retrieval Recall@20 | not established | not established (quota-blocked, n=2) |
| Retrieval oracle ceiling | not established | not established |
| Verifier oracle ceiling (raw NLI, full degating) | 80.25% | untested for LLM verifier at pipeline level |
| Estimated total ceiling | ~80-82% | **still ~80-83%; no tested alternative moves it** |
| Median latency | 382ms | 132ms (LoRA) / 12,930ms (LLM, 34x slower) |
| p95 latency | not separately reported this pass | not separately reported this pass |

## IS A TRUE 95% FINAL RESULT NOW REALISTIC?

# **NO.**

**Exact layer preventing it: the verifier (NLI/stance-recognition
capability).** The quantified gap is precise: raw verifier success must
rise from ~80.25% to ~96.0% (+15.75pp) for the aggregation layer — already
running at ~98.4% efficiency — to deliver 95% end-to-end. Two genuinely
different approaches were tried across this and the prior pass: a modest
fine-tune (+1.95pp, nowhere near enough) and a fundamentally different
"evidence-grounded reasoning" architecture using the one model that could
actually be run in this environment for free (a 26.1-point *regression*,
not an improvement, at 34x the latency). Neither points toward a
plausible path to +15.75pp with resources available here. The retrieval
layer remains a genuine unknown (API-quota-blocked), but the controlled-
evidence dataset — where retrieval is not in question — already shows the
same ~80% ceiling, so even perfect retrieval cannot be the fix by itself.

**Per Phase 22-23's own rule, development validation does not come close
to the required 95%/92%/97% bar across any tested configuration, so no
new 1,000+ case development corpus and no final 500-case holdout were
built.** Building either now would not change this conclusion and would
spend real time confirming a result already established with reasonable
confidence.

No further engineering phase was begun automatically, per the stop
condition.
