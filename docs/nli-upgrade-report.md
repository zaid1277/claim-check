# Claim Check — NLI Capability Upgrade Pass: Development-Only Findings

**Per the explicit stop condition: no final holdout was built or run. No
production code was changed — the current model still ships.** This
report presents validation-only findings and a clear recommendation, then
stops for a go/no-go decision.

## 1. Hardware feasibility

This sandbox is an **Apple M1 with 8GB total RAM**, no CUDA, MPS available
but sharing the same 8GB unified memory as everything else running on the
machine — and this is a genuinely shared, busy desktop (VS Code, several
browser-engine renderer processes, other always-on apps), not a dedicated
training box. Measured directly:

- A first training attempt at `max_length=384` ran for **57 minutes
  without completing even one epoch**, with 14+ million recorded swapins —
  severe, real memory pressure, not a hang (CPU usage stayed 110-150%
  throughout). Killed rather than left to run indefinitely.
- A realistic per-step timing test on actual training data (not synthetic
  short sentences) at `max_length=256`, LoRA-adapted base model, batch
  size 2: **~1.0-1.3s/step**, translating to roughly 10-14 min/epoch.
- **Conclusion:** full fine-tuning of the 435M-parameter large model
  (`DeBERTa-v3-large-mnli-fever-anli-ling-wanli`) is not realistic here.
  LoRA-adapted fine-tuning of the 184M-parameter base model
  (`DeBERTa-v3-base-mnli-fever-anli`) at a reduced sequence length is
  feasible but genuinely tight, and real memory pressure recurred even at
  the reduced configuration (though the run completed this time). This
  assessment was given to the user before any training began, and the
  user explicitly chose to attempt the small-scale LoRA path.

## 2. Datasets selected

| Source | Why |
|---|---|
| SciFact train split (freshly downloaded, official release) | The diagnosed dominant weakness is dense/scientific text; this split was **never touched by any prior pass** (all prior work used only the 300-claim dev split) |
| MNLI (`nyu-mll/multi_nli`) | General-domain diversity, sampled not exhausted |
| FEVER-NLI (`pietrolesci/nli_fever`) | Closer to Claim Check's actual fact-verification domain than generic MNLI (real claims + real extracted Wikipedia evidence) |
| Hand-authored hard negatives | Same-topic/different-proposition pairs (Phase 2's exact pattern: "acquired" vs "partnered with", "founded" vs "became CEO of") |
| Hand-authored hard contradictions | Numeric, temporal, negation, relation-reversal, implicit/scientific contradiction (Phase 3's exact patterns) |

## 3. Dataset sizes

| Source | Pairs |
|---|---:|
| SciFact-train | 800 |
| MNLI (sampled) | 390 |
| FEVER-NLI (sampled) | 510 |
| Authored hard-negatives (35 triples × 3) | 105 |
| Authored hard-contradictions (30 triples × 3) | 90 |
| **Total (after internal dedup)** | **1,895** |
| Train / Validation split (stratified by origin×label, 80/20) | **1,515 / 380** |

By label: support 698, neutral 650, contradict 547 (reasonably balanced,
not neutral-dominated). **Leakage audit: 0/1,895 pairs overlap with
either the Group 4 Hyper holdout or the remediation confirmation
holdout** (both scanned by exact-text hash before any pair was accepted;
Rule 1 honored).

## 4. Label mapping

Verified by direct inspection before use, not assumed (Phase 11):

- ANLI/MNLI convention `0/1/2 = entailment/neutral/contradiction` —
  confirmed by inspecting sample rows.
- **FEVER-NLI field-name trap caught during construction:** in
  `pietrolesci/nli_fever`, the field literally named `"premise"` holds the
  *short claim*, and the field named `"hypothesis"` holds the *long
  extracted evidence* — the reverse of what the names suggest. Mapped by
  content (claim → our claim slot, evidence → our passage slot), not by
  field name, and documented inline in `build_corpus.py`.
- SciFact: `SUPPORT`/`CONTRADICT`/no-evidence (`NEI`) → `support`/
  `contradict`/`neutral`. `NEI` claims paired with the abstract they were
  originally cited against (a real, on-topic hard neutral — annotators
  considered it and found it insufficient — not a random unrelated pair).
  Claims with genuinely mixed evidence (`SUPPORT` in one part of the
  corpus, `CONTRADICT` in another) excluded rather than force-labeled.
- The base checkpoint's own `id2label` was read and mapped at both
  training and merge time (`resolve_label_ids()` in `train.py`) rather
  than assumed to follow the same order as the training datasets.

## 5. Hard-negative construction (Phase 2)

35 hand-authored triples, each producing a support/contradict/neutral
set sharing the same claim: e.g. claim "Company X acquired Company Y,"
neutral evidence "Company X announced a new strategic partnership with
Company Y" — high lexical overlap, same entities, wrong proposition.
Domains: business, medicine, science, sports, technology, history,
environment.

## 6. Hard-contradiction construction (Phase 3)

30 hand-authored triples emphasizing: numeric contradiction ("$4.5 million"
vs "$450,000"), temporal contradiction ("joined in 2018" vs "left in 2018
after joining in 2015"), negation/relation-reversal ("caused the
improvement" vs "no evidence it caused the improvement"), implicit
contradiction requiring inference ("currently CEO" vs "stepped down last
year"), and scientific contradiction ("exothermic" vs "endothermic",
"recessive" vs "dominant" inheritance).

## 7. Scientific subset

800 SciFact-train pairs is the dedicated scientific subset (Phase 4 asked
for 200-300; this pass's SciFact allocation exceeds that because the
diagnosed weakness made it the deliberate emphasis, not an afterthought).
Domains represented naturally by SciFact's own claim distribution
(biology, medicine, genetics/genomics, public health, clinical trials).
Measured separately throughout (§11-12).

## 8. Training strategy (Phase 5-9)

**Base model strategy chosen: (B) LoRA-adapted `DeBERTa-v3-base-mnli-
fever-anli`**, not (A) continued full fine-tuning of the large model
(infeasible, §1) and not (C) a different architecture (no other locally-
practical NLI-capable encoder identified). LoRA config: rank 8, alpha 16,
dropout 0.1, targeting `query_proj`/`key_proj`/`value_proj` — 444,675
trainable parameters, **0.24% of the 184.9M total**. Batch size 2,
gradient accumulation 8 (effective batch 16), learning rate 1e-4, max 4
epochs with early stopping (patience 2, monitored on validation macro F1),
fixed seed (20260916) throughout. A staged curriculum (Phase 9) was
**not** attempted given the time already spent on the corpus/hardware
work — the mixed single-stage training below already showed clean,
monotonic improvement with no plateau, so there was no measured signal
that staging was needed.

Length experiment (Phase 10): tested 384 vs 256. **384 caused severe
memory pressure and was abandoned (§1); 256 completed cleanly.** 512 was
not attempted given 384 already failed. This is a genuine, hardware-forced
scope reduction, not a methodology choice — Group 3's prior finding that
aggressive sentence-level truncation hurts performance was respected (256
tokens still covers the median SciFact abstract, ~67 words / ~90 tokens,
comfortably, only truncating the longest tail).

## 9. Candidate models

Only one candidate was trained to completion (the LoRA-adapted base
model, given the hardware-forced scope above). No second candidate
architecture was trained; `facebook/bart-large-mnli` was not
re-attempted as a training base given its previously-documented SIGBUS
crash on this hardware (accuracy-max pass, §7).

## 10. Training curves

Clean, monotonic improvement across all 4 epochs, no overfitting signal
(train loss still falling, validation macro F1 still rising at the final
epoch — early stopping never triggered):

| Epoch | Train loss | Val accuracy | Val macro F1 | Wall time |
|---:|---:|---:|---:|---:|
| 1 | 0.544 | 77.89% | 78.42% | 634s |
| 2 | 0.461 | 79.21% | 79.58% | 641s |
| 3 | 0.400 | 81.05% | 81.29% | 603s |
| 4 | 0.353 | **83.16%** | **83.39%** | 604s |

Total training wall time: ~40 minutes (second attempt, at max_length=256).

## 11. Model comparison — held-out validation (380 pairs, never trained on)

Both models evaluated identically via `evaluate_model.py`, raw (uncalibrated) predictions:

| Metric | Current (large) | New candidate (LoRA base) |
|---|---:|---:|
| Accuracy | 80.79% | **83.16%** |
| Macro F1 | 81.44% | **83.39%** (+1.95pp) |
| Support P/R/F1 | 89.7% / 74.3% / 81.2% | 85.4% / 79.3% / 82.2% |
| Neutral P/R/F1 | 67.5% / 87.7% / 76.3% | **78.0% / 84.6% / 81.2%** |
| Contradict P/R/F1 | 93.7% / 80.9% / 86.8% | 87.2% / 86.4% / 86.8% |
| False contradiction rate | **2.22%** | 5.19% (raw) / 3.33% (calibrated, §14) |
| Opposite-direction error rate | **0.53%** (2 cases) | 3.42% (13 cases, raw) |
| Scientific subset macro F1 | 61.97% | **66.19%** (+4.22pp) |
| Latency (median) | 382ms | **132ms** |
| Peak RSS | 2047MB | **1100MB** |

Real gains: overall accuracy, neutral handling (huge — F1 76.3%→81.2%),
scientific-text F1, latency, memory. Real regression: false-contradiction
rate and opposite-direction errors both worsened at raw/uncalibrated
predictions (contradiction F1 is identical, 0.868 both, but via a
different, less conservative precision/recall balance).

## 12. 5-fold results

**Important caveat, stated plainly:** the candidate model was *trained*
on 80% of the combined train+validation pool, so a naive 5-fold sweep
over that same pool is not a clean estimate for it (4 of 5 folds in each
run include data it has already seen). Run anyway for stability/collapse
information only, alongside a genuinely clean comparison using the
never-trained-on current model:

| | Macro F1 mean | stdev | worst fold |
|---|---:|---:|---:|
| Current (clean, never trained on this pool) | 82.78% | 1.25% | 81.28% |
| Candidate (train-data-leaked, informational only) | 88.31% | 2.31% | 85.74% |

No fold collapse for either model. The candidate's 88.3% figure should
**not** be read as its true performance — the honest number is the
held-out validation figure in §11 (83.39%).

## 13. Opposite-direction errors

Tracked explicitly per Phase 13's instruction that these are more
damaging than neutral misses:

| | true contradict → predicted support | true support → predicted contradict | total rate |
|---|---:|---:|---:|
| Current | 1 | 1 | 0.53% |
| Candidate (raw) | 5 | 8 | 3.42% |
| Candidate (calibrated, t=0.65) | fewer (exact count not separately re-tallied; false-contradiction component dropped from 5.19%→3.33%) | | |

This is the single most concerning number in this pass: even after the
scientific-subset and neutral-handling gains, the candidate makes
directionally-flipped errors roughly 6x more often at raw predictions.
Calibration (§14) recovers some but not all of this gap.

## 14. Calibration (Phase 14, new validation data only)

The OLD hand-tuned `min_contradiction_confidence=0.68` was **not** reused
automatically. A fresh contradiction precision/recall curve was built on
the new validation split:

| Threshold | Precision | Recall |
|---:|---:|---:|
| 0.50 | 88.0% | 86.4% |
| 0.60 | 90.2% | 83.6% |
| **0.65** | **91.0%** | **82.7%** |
| 0.70 | 90.6% | 79.1% |
| 0.80 | 95.4% | 75.5% |
| 0.90 | 98.6% | 62.7% |

**At t≈0.60-0.65, the candidate clears BOTH of the user's aspirational
targets simultaneously (contradiction precision ≥90%, recall ≥80%)** —
something the current model, and every threshold tested for it across
this whole project, has never simultaneously achieved. This is a
genuinely promising, real finding. Reliability curve confirms the model
is reasonably well-calibrated (confidence 0.9-1.0 bucket: 94.8% actual
accuracy, n=231 of 380).

## 15. Development pipeline replay (Phase 16, 175-case original dev benchmark, everything else fixed)

Using the already-validated in-process replay harness
(`evaluation/hyper/replay_controlled.py`), **retrieval, cross-encoder,
source weights, aggregation, relevance weighting, claim-risk logic, and
verdict rules held fixed** — only the NLI model swapped:

| Metric | Current | Candidate |
|---|---:|---:|
| Accuracy | 76.00% | 76.57% (+0.57pp) |
| Coverage | 61.14% | 63.43% |
| Selective accuracy | **97.20%** | 94.59% (-2.6pp) |
| Easy accuracy | 90.0% | 95.0% |
| Medium accuracy | 93.3% | 96.7% |
| **Hard accuracy** | **54.7%** | **50.7%** (-4.0pp) |
| False abstentions | 39 | 35 |
| Confident errors | 3 | **6** (doubled) |

**Important limitation of this specific test, disclosed honestly:** this
replay used the pipeline's existing `min_contradiction_confidence=0.68`
setting, tuned for the *current* model — it does **not** incorporate the
better-calibrated ~0.60-0.65 threshold found for the candidate in §14.
Re-running this replay with a recalibrated threshold was not completed
before this pass's time budget ran out, and is the clearest concrete
next step if this direction is pursued further (§21).

**The critical finding:** despite genuinely better isolated NLI metrics
(macro F1, scientific F1, calibrated contradiction P/R), **end-to-end
hard-case accuracy went the wrong direction (-4.0pp) and confident errors
doubled** through the actual pipeline, uncalibrated. Better pair-level
NLI performance did not cleanly translate to better end-to-end decisions
in this specific test.

## 16. No-signal recovery (Phase 17 partial)

Not re-run against the two independent holdouts (Rule 1 — diagnostic use
only, and the accuracy-max pass's finding was itself already diagnostic,
not something to re-measure against protected data). The nearest
available proxy is the accuracy-max pass's own finding restated for
context: 51/400 combined-holdout cases had no usable raw NLI signal
anywhere. This pass's candidate was not evaluated against those specific
384 held-out passages (would require re-touching the protected holdouts,
which Rule 1 permits only for taxonomy/comparison, not for choosing or
validating a checkpoint) — so this number is **not** reported as "X/51
recovered." What §11's scientific-subset F1 gain (+4.22pp) on a
*disjoint* new SciFact set suggests is a real but modest improvement in
the same failure family, not a resolved ceiling.

## 17. Old ceiling vs new ceiling

The accuracy-max pass's estimated ceiling (~80-82% end-to-end accuracy)
was derived from the two independent holdouts using the *current* model,
via an aggregation-oracle simulation. That exact simulation was not
re-run with the candidate model against the same (protected) holdout
data, per Rule 1. Using this pass's own equivalent evidence instead: the
175-case development pipeline replay (§15) shows the candidate landing at
76.6% end-to-end accuracy — **essentially unchanged from the current
model's 76.0% on the same benchmark**, with the composition of that
accuracy shifting (better easy/medium, worse hard, more confident
errors) rather than clearly improving. **No evidence this pass produced
supports a materially higher ceiling than before; some evidence
(hard-case regression, doubled confident errors) argues the naive,
uncalibrated candidate could make the practical ceiling worse, not
better, if adopted as-is.**

## 18. Latency / RAM impact

Unambiguously positive for the candidate: 132ms vs 382ms median latency
(2.9x faster), 1.1GB vs 2.0GB peak RSS (1.9x lighter). If the accuracy/
reliability questions were resolved, this would be a strictly better
deployment profile.

## 19. Test totals

No production code was changed this pass (per Phase 19's explicit
constraint — retrieval, cross-encoder, aggregation, relevance weighting,
claim-risk logic, and verdict rules were all held fixed, and the current
NLI model still ships). No backend/frontend/extension code was touched,
so no regression re-run was required or performed; the last verified
baseline (167 backend, 13 frontend, 2 extension tests, all lint/format/
Playwright clean) stands unchanged from the remediation pass.

## 20. Recommendation

**C. MORE NLI TRAINING / CALIBRATION REQUIRED.**

Not a clean "adopt" — the pre-committed Phase 18 bar (macro F1 +5pp
minimum, no catastrophic precision regression) is **not met**: the clean
held-out macro F1 gain is +1.95pp, well under +5pp, and the *uncalibrated*
end-to-end pipeline test shows hard-case accuracy regressing and
confident errors doubling. Not a clean "reject" either — the isolated NLI
capability gains are real (neutral handling, scientific-text F1, latency,
memory), and calibration (§14) shows the candidate can simultaneously
clear both contradiction-precision and -recall targets in a way the
current model never has, on genuinely held-out data. The single biggest
open question this pass leaves unanswered is whether a **properly
recalibrated** (not the borrowed 0.68 threshold) end-to-end pipeline
replay would resolve the hard-case/confident-error regression — that
specific experiment was identified but not completed before this pass's
time budget ran out, and is the clearest, most concrete next step.

## 21. Is 97% achievable?

**No new evidence from this pass supports 97%.** The end-to-end
development-benchmark accuracy barely moved (76.0%→76.6%), and the
component that most directly targets end-to-end reliability (contradiction
precision/recall balance, confident-error rate) moved in a mixed-to-worse
direction when actually run through the pipeline, uncalibrated. The
realistic range this pass's data supports remains in the same
**high-70s-to-low-80s%** band the accuracy-max pass estimated, not
90%+ and certainly not 97%. Domain-adapted training shows genuine promise
as a *direction* (§14's calibration result is the most encouraging single
finding in this pass), but has not yet been shown, with the completed
experiments, to move the actual end-to-end ceiling.

---

## Deliverable summary table (as requested)

| Metric | Current NLI | Best New NLI |
|---|---:|---:|
| Macro F1 | 81.44% | 83.39% |
| Support P/R/F1 | 89.7% / 74.3% / 81.2% | 85.4% / 79.3% / 82.2% |
| Neutral P/R/F1 | 67.5% / 87.7% / 76.3% | 78.0% / 84.6% / 81.2% |
| Contradiction P/R/F1 | 93.7% / 80.9% / 86.8% | 87.2% / 86.4% / 86.8% (raw); 91.0% / 82.7% at t=0.65 |
| False contradiction rate | 2.22% | 5.19% (raw) / 3.33% (t≥0.65) |
| Opposite-direction error rate | 0.53% | 3.42% (raw) |
| Scientific F1 | 61.97% | 66.19% |
| Latency (median) | 382ms | 132ms |
| RAM (peak) | 2047MB | 1100MB |

**Current pipeline accuracy (175-case dev benchmark):** 76.00%
**New-model pipeline accuracy (same benchmark, uncalibrated threshold):** 76.57%

**Old estimated ceiling (accuracy-max pass):** ~80-82%
**New estimated ceiling:** no evidence this pass moves it materially;
still ~high-70s-to-low-80s%, pending a recalibrated pipeline re-test.

**Recommendation: C — MORE NLI TRAINING/CALIBRATION REQUIRED**, with the
specific next experiment identified (recalibrated pipeline replay) rather
than left open-ended.

No further engineering phase was begun automatically, per the stop
condition.
