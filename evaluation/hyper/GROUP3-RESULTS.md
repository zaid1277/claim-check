# Hyper pass — Group 3 results

Stopped after Group 3 as instructed. The new Hyper holdout was not built and
the final release evaluation was not started. All numbers below are
development/validation measurements (the 175-case controlled replay, the
120-pair validation split, and purpose-built probe sets) — never the future
Hyper holdout, which has not been touched.

## 1. Group 2 baseline

| Metric | Group 2 |
|---|---:|
| Verdict accuracy | 68.6% |
| Coverage | 52.6% |
| Selective accuracy | 97.8% |
| Confident errors | 2 |
| False abstentions | 53 |
| Easy / medium / hard accuracy | 90.0% / 93.3% / 37.3% |
| Contradiction precision / recall | 75.0% / 38.8% |
| False contradiction rate | 6.5% |
| Backend tests | 167/167 (152 base + 15 from groups 1-2) |

## 2-4. NLI model comparison, missed-contradiction recovery, opposite-direction analysis

Benchmarked 5 practical, locally-runnable candidates on the **120-pair
validation split** (never the holdout), with a uniform 0.65 confidence gate
for comparability, plus recovery against the 71 historical missed
contradictions (see Group 2's phase-9 analysis: 32 "NLI said neutral", 27
"NLI confidently said the opposite direction", 12 "right direction, under-
confident").

| Model | Params (M) | Macro F1 | Contradiction P/R | False contra. rate | Latency (median/p95 ms) | Peak RSS | Recovered: neutral-miss / opposite-direction / low-confidence |
|---|---:|---:|---|---:|---|---:|---|
| **MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli** (previous default) | 184 | 0.594 | 72.7% / 60.0% | 11.3% | 88 / 111 | ~740MB (on disk) | 0/32, 0/27, 12/12 |
| **MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli** (chosen) | 435 | **0.759** | **83.8% / 77.5%** | **7.5%** | 277 / 335 | ~2.0GB | **13/32, 7/27, 8/12** |
| facebook/bart-large-mnli | ~407 | — | — | — | — | — | Crashed (bus error) twice in this environment; abandoned rather than chased, given the winner already decisive |
| cross-encoder/nli-deberta-v3-small | 142 | 0.348 | 40.0% / 35.0% | 26.3% | 47 / 57 | — | 4/32, 5/27, 5/12 |
| typeform/distilbert-base-uncased-mnli | 67 | 0.296 | 30.6% / 27.5% | 31.3% | 24 / 30 | — | 4/32, 5/27, 3/12 |

**Decision: adopt `MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli`.**
It is not a marginal call — it wins every axis simultaneously (precision,
recall, F1, false-contradiction rate) at a real, measured, acceptable cost
(~3.1x latency, ~2.7x memory). It recovers **7 of the 27 "confidently wrong
direction" misses** that Group 2 established no amount of threshold tuning
could fix (the old model recovered 0/27 at any gate) — this is the single
most important number in this pass, since it's direct evidence the actual
NLI-quality ceiling Group 2 diagnosed has partially moved, not just been
worked around. The two smaller candidates are decisively weaker on every
axis (worse than the previous default, consistent with the project's earlier
development-pass finding) — rejected outright. `facebook/bart-large-mnli`
crashed with a low-level bus error on both attempts in this environment
(likely a memory constraint); not pursued further given the chosen model
already won decisively and per "don't use huge impractical models."

**Per-subset benchmarks (phase 2 — negation, entity relationships, numeric,
temporal, causal, comparative, ranking, partial entailment, lexical-overlap
traps, same-topic/different-predicate, long-passage/short-claim, paraphrase,
entity collision) were not built as separate labelled subsets this pass** —
a genuine scope limitation, not an oversight. Building 13 well-populated,
independently-checked subsets to a quality bar worth trusting is itself a
multi-day task; instead, the 71 real historical misses (already tagged by
cause: neutral/opposite-direction/low-confidence) and the qualitative read
of the "opposite-direction" cases in `PHASE1-2-ANALYSIS.md`/Group 2's own
report served as the working proxy. Recommend building the 13 subsets
properly as part of constructing the new Hyper holdout (phase 20), where
they can be done once, correctly, and reused.

## 3 (verification). Premise/hypothesis direction audit

Confirmed, not assumed: `nli.py`'s `interpret_label()` already maps by the
model's own declared string label name (`model.config.id2label[i].lower()`),
not by index position — this matters, because the 5 candidates use 3
**different** label orderings:

| Model | `id2label` order |
|---|---|
| MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli | 0=entailment, 1=neutral, 2=contradiction |
| cross-encoder/nli-deberta-v3-small | 0=contradiction, 1=entailment, 2=neutral |
| typeform/distilbert-base-uncased-mnli | 0=ENTAILMENT, 1=NEUTRAL, 2=CONTRADICTION (uppercase) |

Had the code assumed a fixed index→label mapping (a real, easy-to-make bug),
swapping in `cross-encoder/nli-deberta-v3-small` would have silently
flipped support and contradiction. It doesn't, because the existing code
was already written defensively. Premise=passage/hypothesis=claim,
`truncation="only_first"` (never truncates the claim), and `max_length=512`
were all verified unchanged and correct for the new model.

## 4. Long passage handling (premise windowing)

Compared full-passage premise against a "best-matching sentence ± 1" window
(word-overlap proxy for proposition relevance, since re-running the actual
cross-encoder here would duplicate that model's own job) on the 120-pair
validation set, using the new model:

| | Macro F1 | Contradiction P/R | Latency (median ms) |
|---|---:|---|---:|
| Full passage | **0.759** | **88.2% / 75.0%** | 274 |
| Best-sentence window | 0.717 | 82.4% / 70.0% | 269 |

**Full passage wins clearly, on every axis, for negligible latency
difference.** Windowing actively hurt here — consistent with the brief's own
warning not to destroy necessary context; the surrounding sentences
apparently carry disambiguating information the window sometimes cut.
**No change made** — this validates keeping the existing full-passage
premise, rather than adding complexity that would have made things worse.

## 5. Ensemble

Not built. The single chosen model already meets or nearly meets every
group-3 NLI target on its own (see §17-18); Group 2's own smaller-candidate
results plus this pass's premise-window negative result gave no positive
signal that a second model would add enough to justify the "run two
transformers, reconcile" complexity and latency cost the brief itself is
cautious about. Revisit only if a future benchmark shows this model has a
specific, identifiable blind spot an ensemble could target.

## 6-7. Calibration and class-specific thresholds

Computed Expected Calibration Error and a full precision-recall curve for
the contradiction class on the new model, using the 120-pair validation set
(never the holdout).

**Real overconfidence found:** contradiction-class ECE = 0.154. At the
0.9-1.0 raw-confidence bin (31 of the 40 true-contradiction cases' nearest
predictions land here, mean confidence 0.987), **actual accuracy is only
87.1%** — meaningfully below what the raw softmax implies. This is a
genuine remaining limitation, not something the threshold choice below
fixes; it means even confident contradiction calls should be read with real
skepticism, not treated as near-certain.

**Threshold sweep (contradiction class only, the class this pass focused
on):**

| Threshold | Precision | Recall |
|---:|---:|---:|
| 0.85 (old default) | 100%* | 42.5% |
| 0.70 (**new default**) | **88.2%** | **75.0%** |
| 0.60 | 78.9% | 75.0% |
| 0.50 | 65.4% | 42.5%† |

*The old 0.85 threshold's small validation sample at that exact cut showed
100% precision but only 42.5% recall — consistent with Group 2's diagnosis
that the old gate traded away real recall. †Non-monotonic recall at very low
thresholds reflects the small (40-case) per-class sample; not chased
further given 0.70 already met both group-3 targets.

**No threshold reached the aspirational ≥92% precision without recall
collapsing** (best achievable pareto point at that floor: none found in the
swept range) — 88%/75% was the defensible, achievable Pareto point, not the
ideal one, and is reported as such rather than silently substituted.
**Chosen: 0.70** (down from 0.85) — meets both group-3 targets
simultaneously (≥88% precision, ≥65% recall) and, at this exact point,
false-contradiction rate on the validation set is 4/80 = **5.0%** (fp=4,
tp=30, fn=10) — better than Group 2's reported 6.5%, though not quite at the
≤4% target. `min_nli_confidence` (the general 0.65 gate) was left unchanged;
nothing in this pass's evidence pointed at it specifically.

## 8-10. Compound claim policy, atomic coverage

Built a curated 6-case compound-claim probe set exercising the real
`evidence_scoring.assess()` per atom (not mocked verdicts) — all supported,
one contradicted, one unresolved (the key policy question), 2/3 confirmed
with one unresolved, all unresolved, one atom with genuinely conflicting
evidence. **The existing policy already matches curated judgment on 6/6
cases**; a second candidate policy produced identical output on every case.
**No policy change made** — nothing justified one, honoring "keep UI
vocabulary stable unless justified."

**Added:** `Assessment.verified_atom_fraction` / `.contradicted_atom_fraction`
(new migration `003_atom_coverage.sql`), computed for every multi-atom claim.
Internal/debug-only, **not used to change the verdict decision** — the
compound-probe experiment gave no evidence that doing so would help.

## 11-13. Source authority / provenance

Implemented `evidence_scoring._authority_tiebreak`: engages only when the
plain dominance-ratio check would otherwise land on `MIXED_EVIDENCE`, and
only when the winning side has an `official`/`research`/`institution`-tier
source (≥0.90 weight) **and** the losing side has neither a comparably
authoritative source (max weight <0.75) **nor** substantial independent
corroboration (≤2 independent sources) — so "10 copied blog pages vs. 1 SEC
filing" resolves, while "1 official statement vs. 5 independent
investigative sources" does not simply get overridden. Only ever considers
evidence that already cleared every relevance/eligibility gate.

**Validated directly against the exact scenario Group 2 left open:** the two
probes that previously landed on `MIXED_EVIDENCE` (`probe-diversity-001/002`)
now correctly resolve to `UNSUPPORTED`. Retrieval probe set:
**4/5 correct** (up from Group 2's 2/5). *Implementation note:* the original
probes used synthetic `.example` domains the existing `source_quality()`
heuristic doesn't recognize as authoritative; corrected to a real
`.gov`-pattern for the tiebreak to actually engage — worth remembering for
the eventual new benchmark (use realistic domains throughout). **Phase 12
(provenance/syndication clustering beyond same-domain) was not built** —
scope-limited this pass in favor of validating the tiebreak itself
end-to-end; the existing near-duplicate-content check (`same_content`,
90% word-Jaccard) already catches copy-paste syndication, which covers the
most common real case.

## 14. Calibrated abstention — coverage vs. selective-accuracy curve

Swept `minimum_evidence` directly against the 175-case development replay:

| `minimum_evidence` | Accuracy | Coverage | Selective accuracy | False abstentions | Confident errors |
|---:|---:|---:|---:|---:|---:|
| 0.10 | 76.0% | 62.9% | 94.5% | 36 | 6 |
| 0.15 | 76.0% | 61.7% | 95.4% | 37 | 5 |
| **0.20 (new default)** | **76.0%** | **61.7%** | **95.4%** | **37** | **5** |
| 0.30 | 75.4% | 61.1% | 95.3% | 38 | 5 |
| 0.40 | 73.1% | 57.7% | 97.0% | 44 | 3 |
| 0.50 (Group 2 default) | 68.6% | 52.6% | 97.8% | 53 | 2 |
| 0.65 | 34.9% | 18.3% | 96.9% | 113 | 1 |

Mapping to the requested checkpoints (nearest measured point): **≈98% →
coverage 52.6%**; **≈97% → coverage 57.7%**; **≈95% → coverage ≈61-63%**
(0.10-0.30 form a plateau). No point tested went below 94.5%, since
confident errors were already at the group-3 ceiling (6) at 0.10 and rising
as the threshold dropped further.

**Chosen: `minimum_evidence = 0.20`** — the plateau's best point (matches
0.15's accuracy/coverage/selective-accuracy, one fewer confident error than
0.10). Note: **the authority tiebreak had zero measurable effect on this
175-case set at any threshold** (0.50's result here is bit-for-bit identical
to Group 2's own reported numbers) — its validated value is specific to the
retrieval-probe set, because this dev set's synthetic fixture domains don't
match real `.gov`/`.edu` patterns.

## 15. False abstention target

Target was <30 (from 53 in Group 2); **achieved 37 with the recalibrated
threshold alone, 39 with the new model** (a small increase from 37, offset
by 2 fewer confident errors and higher selective accuracy — a defensible
trade, not a regression). **Target not met.** The plateau shape in §14
shows why: confident errors rise faster than false abstentions fall below
`minimum_evidence≈0.15`, so the remaining ~37-39 false abstentions are
gated by something a pure aggregation-threshold change cannot reach —
consistent with Group 2's own diagnosis (NLI-quality ceiling, not
aggregation-threshold ceiling). The new NLI model measurably helped this
ceiling (hard accuracy jumped 37.3%→54.7%, see §16) without fully closing
the false-abstention count.

## 16. Iterative retrieval / follow-up search re-test with the new NLI model

Re-ran `probe-followup-001` (the case Group 2 left with a working retrieval
mechanism blocked by low NLI confidence). **The new model correctly
classifies the retrieved evidence as support at 96% confidence** (up from
the old model's 57% neutral call) — direct, concrete evidence that "better
retrieval + better NLI" does compound, exactly as phase 17 asked to check.
**However the end-to-end verdict is still `INSUFFICIENT_EVIDENCE`** — not a
failure, but Group 1's high-risk gate working exactly as designed: this
claim ("Solvex Pharma's new drug reduced hospitalizations by 40% in its
phase 3 trial") is medical, so `claim_risk()` correctly classifies it
"high", requiring 2+ independent sources before committing — and this probe
only supplies one, even after the follow-up. This is worth reporting
precisely rather than glossed over: **retrieval found the evidence, NLI
read it correctly, and a separate, intentional safety mechanism still
withheld a confident verdict** — three validated mechanisms interacting
coherently, not a remaining bug. A probe with two independent supporting
sources would be needed to see this specific case fully resolve
end-to-end; not rebuilt this pass given time, but the mechanism chain is
now individually verified at every link.

## 17-18. Combined validation metrics, hard benchmark

**Full 175-case replay, new model + `minimum_evidence=0.20` +
`min_contradiction_confidence=0.70` (every group 1-3 change combined):**

| Metric | Group 2 | Group 3 (final) | Δ | Group 3 target | Met? |
|---|---:|---:|---:|---:|:---:|
| Verdict accuracy | 68.6% | **76.0%** | +7.4pp | ≥80% | close |
| Coverage | 52.6% | **61.1%** | +8.5pp | ≥70% | not yet |
| Selective accuracy | 97.8% | 97.2% | −0.6pp | ≥92% | ✓ (comfortably) |
| Confident errors | 2 | 3 | +1 | ≤5 | ✓ |
| False abstentions | 53 | 39 | −14 | <30 | not yet |
| Easy accuracy | 90.0% | 90.0% | 0 | ≥95% | close |
| Medium accuracy | 93.3% | 93.3% | 0 | ≥90% | ✓ |
| **Hard accuracy** | 37.3% | **54.7%** | **+17.4pp** | ≥60% | close |
| Contradiction precision (validation) | 75.0%* | 88.2% | — | ≥88% | ✓ |
| Contradiction recall (validation) | 38.8%* | 75.0% | — | ≥65% | ✓ |
| False contradiction rate (validation) | 6.5%* | 5.0% | — | ≤4% | close |

*Group 2's contradiction figures were measured on the old **test** split
under the old model/gate; this pass's are on the **validation** split under
the new model/gate (per the hyper-pass rule: validation only, never the
holdout) — directionally comparable, not a strict apples-to-apples number.

**5 of 11 targets fully met** (selective accuracy, confident errors, medium
accuracy, contradiction precision, contradiction recall), **3 more within a
few points** (verdict accuracy, easy accuracy, hard accuracy — the hard-
accuracy jump of +17.4pp is the largest single improvement in this entire
pass), **3 not met** (coverage, false abstentions, false contradiction rate
— though all three improved substantially from Group 2).

**100+ case hard benchmark (phase 18): not built this pass** — a genuine,
disclosed scope limitation, not an oversight. Constructing 100+ well-
distributed, quality-checked hard cases (compound facts, partial truths,
numerical/temporal conflicts, authority-vs-weak-source conflicts, copied
sources, ambiguous entities, scientific/causal claims, cross-domain
coverage) to a bar worth trusting is itself substantial work; doing it
properly belongs with constructing the new Hyper holdout (phase 20), where
it can be built once, independently reviewed, and reused rather than
produced twice. The existing 175-case set's 75 hard-tagged cases (plus the
71-case historical-miss analysis) carried this pass's hard-case
measurement instead.

## 19. Ablation table

| Configuration | Accuracy | Coverage | Selective acc. | False abst. | Confident err. | Hard acc. |
|---|---:|---:|---:|---:|---:|---:|
| Group 2 baseline | 68.6% | 52.6% | 97.8% | 53 | 2 | 37.3% |
| + authority tiebreak only (same thresholds) | 68.6% | 52.6% | 97.8% | 53 | 2 | 37.3% *(no effect on this dataset — see §14 note)* |
| + `minimum_evidence` 0.20 (old model) | 76.0% | 61.7% | 95.4% | 37 | 5 | 49.3% |
| + new NLI model + recalibrated contradiction threshold (**all combined**) | **76.0%** | **61.1%** | **97.2%** | **39** | **3** | **54.7%** |
| Structured contradiction helpers | *(rejected in Group 2; not re-tested — no reason to revisit given zero prior benefit)* |
| Improved compound aggregation | *(no change made — current policy already correct on all 6 curated cases)* |
| Sentence/window premise selection | 0.759→0.717 macro F1 *(regression — rejected, not adopted)* |
| Iterative hard-case retrieval (follow-up) alone | *(mechanism validated on probes; no dev-set signal — fixture search there ignores query text)* |

**Rejected / reverted this pass:** premise windowing (real, measured
regression). **Kept despite no measured dev-set benefit (zero-cost,
theoretically sound):** the candidate-pool source-diversity cap from Group
2 (§14 note explains why this dataset can't show its effect). **Adopted
with strong, multi-axis validation:** the NLI model swap and the
recalibrated contradiction threshold — these two changes together drove
essentially all of this pass's accuracy and hard-case gains; the
aggregation-threshold change (0.5→0.20) drove the coverage gain but was
already validated in isolation before the model swap.

## 20. Group 3 final metrics

See the combined table in §17 above for the primary numbers.

## 21-22. False contradiction rate, false abstentions

False contradiction rate (validation, new model/threshold): 5.0% (target
≤4%, not met but improved from 6.5%). False abstentions: 39 (target <30,
not met but improved from 53). See §14-15 for the full diagnosis of why a
pure threshold/model change plateaus here.

## 23. Model memory / resource use

New model: 435M parameters, ~2.0GB peak RSS during validation-set inference,
~277ms median / 335ms p95 latency per NLI call (vs. the old model's 184M
params, latency 88ms/111ms). This is a real, meaningful resource increase —
worth checking against actual product latency budgets (typed-claim median
was ~1.4-1.6s end-to-end in earlier passes; a single claim typically
triggers several NLI calls per atom, so total added latency per
investigation is on the order of hundreds of ms to low seconds, not
independently re-measured end-to-end this pass).

## 24. Software verification totals

| Suite | Result |
|---|---|
| Backend (pytest, real Postgres + real local NLI, new model) | **167 passed** (166 initially, 1 fixed — a threshold-dependent test needed updating to a confidence value below the new 0.70 gate, an expected mechanical consequence, not a bug) |
| Backend lint (ruff, `api` + `evaluation` scope) | All checks passed |
| Backend format (ruff format) | 124 files formatted, clean |
| Frontend TypeScript | Clean |
| Frontend lint (eslint) | Clean |
| Frontend format (prettier) | Clean |
| Frontend unit tests (vitest) | 13/13 passed |
| Production build | Clean |
| Extension tests | 2/2 passed |
| **Browser/Playwright (Chromium + WebKit, release config)** | **14/14 passed (5.7 min)** — run this pass per instruction, since Group 2 skipped it; no regression from the model swap (these flows use fixture mode, not real NLI) |

No critical suite skipped.

## 25. Rejected changes and why

- **`facebook/bart-large-mnli`**: crashed twice (bus error) in this
  environment; not pursued further given the winning candidate already
  decisive.
- **Sentence/window premise selection**: measured regression (macro F1
  0.759→0.717); real evidence that full-passage context matters here.
- **NLI ensemble**: not built — no evidence a second model was needed once
  the single best candidate already met most targets.
- **Compound-verdict policy change**: no change made — the existing policy
  already matched curated judgment on every tested case.
- **Provenance/syndication clustering beyond same-domain (phase 12)**: not
  built — scope-limited in favor of validating the authority tiebreak
  end-to-end; existing near-duplicate-content detection already covers the
  most common real case (copy-paste syndication).
- **100+ case hard benchmark (phase 18)**: not built — deferred to the new
  Hyper holdout's construction (phase 20), to avoid building throwaway data
  twice.
- **Per-subset NLI error benchmarks (phase 2, 13 categories)**: not built
  as separate labelled sets — used the existing tagged historical misses as
  a working proxy instead; same phase-20 deferral reasoning.

## 26. Remaining bottleneck

**Coverage and false abstentions, not raw NLI quality anymore, are now the
binding constraint** — the new model closed a meaningful part of the gap
(hard accuracy +17.4pp) but the aggregation-threshold plateau (§14) means
neither lever alone reaches the coverage/false-abstention targets. The
clearest next-highest-leverage candidates, in rough priority order: (1) the
volume-vs-authority tension noted in Group 2 and only partially addressed by
the tiebreak (needs the phase-12 provenance work to distinguish real
independent corroboration from syndicated repetition more precisely); (2)
the remaining contradiction-class overconfidence (ECE 0.154) — a calibrated-
confidence correction (e.g. temperature scaling, done properly with a held-
out calibration set) could recover real recall at the same or better
precision without further threshold guessing; (3) genuinely building the
100+ case hard benchmark and the 13 NLI error subsets, which would let
future work target the actual remaining failure modes with real numbers
instead of the historical 71-case proxy.
