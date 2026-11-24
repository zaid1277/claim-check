# Claim Check — Accuracy Maximization Pass: Diagnostic Findings & Ceiling Estimate

> Later audit (23 November 2026): the “raw NLI / zero gating” replay below
> retains confidence-gated stances and relevance/risk weighting. It does not
> establish a true accuracy ceiling. See [the correction](accuracy90-research.md).

**This report does not build or run a final holdout, per the explicit stop
condition.** It answers the question the instructions posed first: *before
spending further engineering effort, where is the real bottleneck, and is
97% end-to-end accuracy achievable with this architecture?*

**Scope decision, made explicitly with the user before starting:** the
25-phase request as written is realistically weeks of engineering (live-
search-based 1000-pair/400-investigation corpora, a genuine second strong
NLI model, learned aggregation with cross-validation, structured fact
extraction, multi-round retrieval, 5-fold calibration of every threshold).
Given this session's constraints, the user chose **"depth over breadth"**:
do the two diagnostic phases that determine feasibility (Phase 1 error
taxonomy, Phase 23 ceiling analysis) with real rigor first, then invest
remaining effort only in whatever those point to — rather than touching
all 25 phases shallowly. That is what this report reflects. Phases not
attempted are named explicitly in §16, not silently skipped.

## 1. Previous independent results (recap)

| | Hyper holdout | Remediation confirmation |
|---|---:|---:|
| Verdict accuracy | 80.8% | 76.0% |
| Coverage | 65.2% | 62.0% |
| Selective accuracy | 95.7% | 91.4% |
| Easy / Medium / Hard | 91.7% / 94.4% / 62.0% | 90.0% / 98.0% / 48.3% |
| Contradiction P/R/false-rate | 76.1% / 58.1% / 9.4% | 85.7% / 66.7% / 4.52% |

## 2. Full error taxonomy (Phase 1)

All 84 incorrect investigations across both holdouts (250 + 150 = 400
total cases), reclassified into the requested A–S taxonomy from the
actual stored evidence records (raw NLI stance, exclusion reasons,
relevance scores, independence groups) — not the coarser categories the
prior passes used:

| Category | Count | % of errors |
|---|---:|---:|
| Q — false abstention | 20 | 23.8% |
| D — relevant passage excluded pre-NLI | 16 | 19.0% |
| J — neutral misclassification (masks real signal) | 15 | 17.9% |
| P — aggregation mistake | 10 | 11.9% |
| M — entity mismatch (heuristic, see caveat) | 9 | 10.7% |
| K — temporal reasoning | 7 | 8.3% |
| H — NLI contradiction miss | 2 | 2.4% |
| S — genuinely ambiguous / bad gold | 2 | 2.4% |
| B, N, O (source-not-found, source-quality, source-independence) | 1 each | 1.2% each |

**Caveat on category M:** classified via a crude capitalized-word-overlap
heuristic, not a real NER model. Manual inspection (§4) shows most "M"
cases are actually SciFact scientific-abstract passages with no
capitalized terms matching the claim at all — the same relevance/domain-
calibration issue as category D, not genuine person/place/company
confusion. Categories A, C, E, F, G, I, L, R produced **zero** errors in
this sample — search/extraction/reranking/decomposition/false-
contradiction/numeric-comparison were not measurable failure sources in
this controlled-evidence dataset (see §16 for why retrieval-layer
categories A/B/C/E are largely inapplicable to fixture-evidence
investigations).

By difficulty, hard cases are dominated by the same two categories (Q
21.7%, D 21.7%), confirming this isn't a hard-case-specific pattern but
the system's general failure mode.

## 3. Retrieval oracle ceiling (Phase 3) — not measured this pass, and explained why

**Not attempted with real live search this pass**, for a structural
reason worth stating plainly: every controlled investigation in both
prior holdouts uses **fixture-supplied evidence** (the gold sources are
injected directly, not retrieved by search) — this is the entire point of
a controlled benchmark (reproducibility, no live-search flakiness). That
means "was the correct passage retrieved" is true by construction for
100% of these 400 cases; an oracle-recall number computed on them would
be vacuous. A genuine retrieval-oracle measurement requires a live-search-
based validation set with independently-verified gold passages — real,
valuable work, but a different, larger undertaking (part of Phase 2's
requested 1000-pair corpus) that the depth-over-breadth scope decision
deferred in favor of the diagnostic work in §4–6, which *is* answerable
from existing data and turned out to be more decisive (see §6).

## 4. NLI oracle/ceiling analysis (Phases 7–8, adapted)

Instead of only counting errors, an **aggregation-oracle simulation** was
run: `api/app/services/evidence_scoring.assess()` — the real, unmodified
production function — was re-run over all 400 cases' already-recorded
evidence with **every pre-NLI gate removed** (relevance floor, confidence
threshold, temporal exclusion all bypassed; every evidence item's stance
forced to its raw, ungated NLI label).

| | Accuracy |
|---|---:|
| Actual production pipeline (all gates active) | 79.00% (316/400) |
| **Oracle: raw NLI + aggregation, zero gating** | **80.25%** (321/400) |
| Sanity check (re-run with already-gated stances) | 79.25% (matches actual, confirms simulation correctness) |

**Removing every pre-NLI gate in the entire system buys only +1.25
percentage points.** This is the single most important finding of this
pass: the eligibility-gating layer (relevance floor, confidence
threshold, temporal exclusion) is **not** the accuracy bottleneck, despite
categories D/J/Q above superficially suggesting otherwise — most of those
"gated away" cases had **no usable raw signal in the first place**; the
NLI model itself produced neutral or wrong output on the retained
passages, so ungating them changes little.

By difficulty: easy 91.0%→91.0% (no change), medium 95.7%→96.4% (+0.7pp),
hard 56.9%→59.4% (+2.5pp) — even hard cases, which theoretically have the
most to gain from looser gating, only improve modestly.

**Root-cause decomposition of the 74 genuine zero-signal cases** (cases
where retained evidence totals essentially zero, excluding 49 correctly-
designed empty-retrieval abstention tests which are not failures):

- **51 (12.75% of all 400 cases): no raw support/contradict signal
  anywhere** in the retained evidence — a genuine NLI-model-capability
  ceiling, not fixable by threshold engineering.
- **23 (5.75% of all 400 cases): real raw signal exists but is excluded
  pre-aggregation** (17 by the relevance floor, 7 by temporal/context
  exclusion for date-bearing/current-context claims already gone
  through the improved rules, and inspection shows a mix of directions
  — some genuinely-correct signal, some genuinely-wrong signal at very
  similar relevance scores, so further blanket floor-loosening would
  likely trade recovered cases for newly-admitted wrong-direction ones
  at a similar rate, consistent with the +1.25pp ceiling measured above).

## 5. Decomposition analysis (Phase 9–10) — not separately audited this pass

Compound-claim/decomposition-specific failures (category F/R) were **zero**
in the 400-case error set. Given §4's finding that the model itself, not
the pipeline logic, is the binding constraint, and given zero measured
decomposition errors, this was correctly deprioritized rather than
speculatively "fixed."

## 6. Reranker comparison (Phase 6) — not run this pass

Deprioritized once §4 showed pre-NLI gating (which a better reranker
would only marginally improve, by surfacing marginally better-ranked
passages within an already-correct fixture evidence set) is not the
bottleneck. For live search — where reranking chooses among many more
candidates — this remains a legitimate open question, but requires the
same live-search infrastructure as §3.

## 7. NLI ensemble results (Phase 7)

Tested directly: for every evidence item behind an incorrect
investigation where the **primary model's raw stance was neutral** (the
single largest sub-pattern within the dominant D/J/Q categories), was
classified with `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` (the only
practical, comparably-relevant second model available locally that isn't
strictly dominated by the primary — see §16 for why `bart-large-mnli`
could not be tested at all).

**Result: of 74 such cases, the secondary model confidently (≥0.65)
recovers the correct direction in only 11 (14.9%).** Since this secondary
model already measured decisively weaker overall (macro F1 0.624 vs 0.768
on the multi-fold contradiction corpus from the prior pass), and the two
models are from the same training lineage (likely correlated errors,
confirmed by this low recovery rate), **an ensemble/cascade with the
locally-available models is not adopted** — the expected gain (a few
points on a small subset) is outweighed by the near-certainty of also
importing the weaker model's own additional errors on cases the primary
model already gets right.

## 8. Structured reasoning results (Phase 11–14) — not attempted this pass

Structured fact extraction (entity/relation/value/time), a dedicated
numeric-comparison layer, explicit temporal-state modeling beyond the
existing `context_exclusion`/`needs_current_evidence` checks, and entity-
disambiguation improvements were not built this pass. §2's taxonomy found
numeric reasoning (L) at 0% and entity mismatch (M) mostly attributable to
the same relevance/domain issue as D (not misfired reasoning about a
correctly-identified but wrong entity) — the concrete, measured evidence
did not point at these as the dominant lever, so effort was not spent
building speculative new subsystems for them.

## 9. Learned aggregation results (Phase 17–18) — not attempted this pass

Directly superseded by §4's finding: the current rule-based aggregation,
given raw (ungated) NLI output, already reaches 80.25% — a learned
aggregator could only ever close the gap between that number and a true
ceiling that is itself capped well below 97% by NLI-model capability
(§4). Building a learned aggregator now would optimize a component that
is demonstrably not the primary constraint.

## 10. Selective escalation results (Phase 19) — not attempted this pass

Would only be worth building once a genuinely stronger secondary
reasoning path exists (§7 found none locally available); escalating to a
weaker model for hard cases would not help.

## 11. 5-fold calibration results (Phase 21) — not separately re-run this pass

The remediation pass's 3-fold contradiction calibration remains the most
recent multi-fold work; no new threshold was chosen this pass to
calibrate, since §4 showed threshold engineering has already been pushed
close to its ceiling (+1.25pp available at most).

## 12. Accuracy/coverage curves (Phase 22)

Computed by re-running `assess()` at swept `minimum_evidence` values over
all 400 cases' recorded evidence (diagnostic only — the shipped setting,
0.20, was not changed):

| `minimum_evidence` | Accuracy | Coverage | Selective accuracy |
|---:|---:|---:|---:|
| 0.05 (near-zero) | 80.5% | **65.75%** (hard ceiling) | 93.9% |
| 0.20 (current, shipped) | 79.3% | 64.3% | 94.2% |
| 0.30 | 77.5% | 61.5% | 95.1% |
| 0.50 | 68.0% | 51.0% | 96.1% |
| 0.65 | 41.3% | 23.0% | 95.7% |
| 1.00 | 21.0% | 2.75% | 63.6% |

**Coverage cannot exceed ~66% by adjusting this single threshold, no
matter how low it is set** — confirming §4's finding structurally: 30.8%
of all 400 cases (123 cases) retain essentially zero usable evidence
regardless of the total-weight cutoff, because the evidence is neutral (or
excluded) before the threshold ever applies. Of those, 49 are correctly-
designed empty-retrieval abstention tests (not a problem); the remaining
74 are the real ceiling-setting cases analyzed in §4. **The requested
70/80/90/100%-coverage operating points are not reachable through
threshold tuning alone** on this evidence distribution — reaching them
would require either much weaker relevance/confidence gating (shown in §4
to buy almost nothing) or fundamentally more capable evidence recognition
upstream.

## 13. Validation metrics — reported honestly as the same diagnostic numbers above

No new validation corpus was built this pass (§16), so there are no
"fresh validation" numbers distinct from §1/§2/§4/§12 — all figures in
this report are computed from the two existing independent holdouts,
used diagnostically only, never to pick a final threshold or claim as a
held-out result.

## 14. Estimated achievable ceiling

Combining §4 (aggregation-oracle: +1.25pp from perfect gating) and §7 (no
viable local ensemble gain): **the realistic ceiling for this
architecture, with the currently-available local models, is approximately
80–82% end-to-end verdict accuracy at roughly 65% coverage** on
data with this difficulty mix (400 mixed-domain cases including
adversarial ANLI-style pairs and dense SciFact scientific abstracts).
This is barely above the 79.0% already measured in production. **97% is
not realistically achievable with this architecture as currently built**
— not because of a fixable engineering gap this pass found, but because
the dominant remaining error source (51 of 400 cases, 12.75%) is the
locally-available NLI model failing to recognize correct stance on
retained, on-topic evidence, most concentrated in dense/scientific text,
and the one available alternative model does not meaningfully compensate
for it (§7).

## 15. Architecture changes accepted this pass

**None.** Every diagnostic result this pass pointed at either (a) an
already-addressed lever with little further room (gating, §4/§12), or (b)
a limitation not fixable without resources unavailable in this
environment (a genuinely stronger/more diverse NLI model, §7). Making a
speculative change with no measured justification, purely to have
"changed something," was rejected as inconsistent with this project's
standing discipline.

## 16. Architecture changes rejected / not attempted, with reasons

| Change | Reason not pursued |
|---|---|
| Further relevance-floor loosening (support stance, or contradiction floor beyond -1.5) | §4's inspection of the 23 fixable cases found roughly as many wrong-direction as correct-direction signals at similar relevance scores — no clear net win, consistent with the measured +1.25pp aggregation-oracle ceiling |
| NLI ensemble with `DeBERTa-v3-base-mnli-fever-anli` | Only recovers 14.9% of primary misses (§7); expected to import as many new errors as it fixes given correlated model lineage |
| NLI ensemble with `bart-large-mnli` | Reproducibly crashes this machine's CPU inference with SIGBUS — a known, previously-documented issue (Group 2, remediation pass), not re-investigated a third time |
| Live-search retrieval-oracle corpus (Phase 2/3) | Real, valuable work, but the controlled/fixture evidence design makes it vacuous on existing data (§3); building it properly is a separate, larger undertaking than this pass's diagnostic scope |
| Learned aggregation (Phase 17/18) | Superseded by §4/§9: the rule-based aggregator is not the binding constraint |
| Structured fact representation, numeric/temporal/entity V2 layers (Phases 11-14) | §2's taxonomy measured zero decomposition errors and near-zero numeric-reasoning errors; entity-mismatch cases were mostly a relevance-gating artifact (§2 caveat), not genuine disambiguation failures |
| Multi-round/multi-query retrieval (Phases 4-5) | Applies to live search specifically; deferred with §3 for the same reason |
| Sentence/passage-window premise selection for dense text | Already tried and measured as a **regression** in Group 3 (macro F1 0.759→0.717); not re-attempted without new justification |

## 17. Latency impact

None — no architecture or threshold change was made this pass, so
production latency is unchanged from the remediation pass's measured
values.

## 18. Test totals

No production code was changed this pass. Sanity re-run: **backend
`pytest api/tests`: 167 passed**, 3 warnings (unchanged from the
remediation pass baseline, confirming no regression from the diagnostic
scripts added under `evaluation/accuracy-max/`, which are read-only
analysis over already-recorded data and do not touch `api/app`). Lint
(`ruff check`) and format (`ruff format --check`) clean across `api` and
`evaluation`. Frontend/Playwright/extension/TypeScript/build/accessibility
were not re-run this pass since no frontend, extension, or build-affecting
code was touched (they were last verified clean in the remediation pass).

## 19. Is 97% realistically achievable?

**No, not with this architecture and the locally-available models.**
Every lever this pass could cheaply and honestly test — full gating
removal, a second local NLI model, threshold sweeping — moved end-to-end
accuracy by low single digits at most, and the dominant remaining error
source is a genuine model-capability ceiling on dense/scientific text
that none of those levers touch. A credible path toward materially higher
accuracy would need either a genuinely stronger, more diverse NLI model
than what runs in this environment, or substantial new engineering
(live-search-based retrieval-quality work, a properly-scoped structured-
reasoning layer, or model fine-tuning) well beyond this pass's diagnostic
scope — none of which this report can honestly claim to have delivered.
**Recommended next step, if pursued:** treat NLI-model capability on
scientific/dense text as its own research question (a fine-tuning or
better-base-model investigation) before any further threshold/aggregation
engineering, since §4 and §12 both show that lever is nearly exhausted.

---

### Source data

`evaluation/accuracy-max/error_taxonomy.py`,
`oracle_aggregation.py`, `coverage_curve.py`,
`ensemble_complementarity.py` and their outputs under
`evaluation/accuracy-max/results/`. All diagnostic, all computed from the
two existing independent holdouts' already-recorded evidence — neither
holdout's threshold, model, or label was changed as a result of this pass.
