# Hyper pass — Group 2 (Phases 8-16) results

Stopped after Group 2 as instructed. Group 3 has not started.

## 1. Group 1 baseline metrics (for reference)

| Metric | Value |
|---|---:|
| Verdict accuracy | 68.0% |
| Coverage | 52.6% |
| Selective accuracy | 96.7% |
| False abstentions | 53 |
| Confident errors | 3 |
| Easy / medium / hard accuracy | 90.0% / 93.3% / 36.0% |

## 2. Contradiction miss analysis

**Pair-level (348-case NLI holdout, now development evidence), 71 missed
contradictions**, classified by the actual stored `raw` NLI label (not
inferred):

| Cause | Count | % |
|---|---:|---:|
| D — NLI's raw top label was neutral | 32 | 45.1% |
| E — NLI's raw top label was support (opposite direction) | 27 | 38.0% |
| F — raw label was contradict but confidence below the 0.85 gate | 12 | 16.9% |

This is a materially different picture than the coarser "NLI prediction:
57 / NLI confidence: 5" bucket reported in the final evaluation: **38% of
misses are the model being confidently wrong in the opposite direction**, not
merely under-confident — no amount of threshold relaxation fixes those; only
an independent signal can. Full per-case detail (claim, passage, raw label,
confidence, probabilities):
`evaluation/hyper/missed-contradictions-pairs.json`.

**Product-level (175-case controlled replay)**: zero false abstentions had
empty retrieved evidence; the dominant cause (60% of all 95 original false
abstentions) was a single-source evidence-scoring shortfall, already fixed in
Group 1 — see `evaluation/hyper/PHASE1-2-ANALYSIS.md`.

Qualitative read of the 27 "raw predicted support" pair-level misses: many
are genuinely adversarial ANLI phrasing (digit-sum puzzles, implicit duration
arithmetic, entity disambiguation) rather than clean structural
number/date/location swaps — this shaped the structured-helper result below.

## 3-4. Structured helper design and numerical/temporal/location results

Built `api/app/services/structured_contradiction.py`: reuses the existing
spaCy pipeline (already a dependency) for entity/money/percent/date
recognition, fires only when claim and passage share a named entity (or, for
negation, share ≥50% content words) *and* a matching predicate context, and
only on money (>10% relative difference), percentages (>2pp), single-year
temporal claims (skipped entirely for claims needing current evidence, and
requiring lexical overlap ≥0.2 so a shared predicate keyword can't paper over
two different events), single-GPE location claims, and negation. 9/9 unit
tests pass, including explicit guards against the failure modes the phase-10
brief warns about (topic-only overlap, unrelated entities, "different year =
contradiction" for a currentness claim).

**Measured, not assumed:**

| Test | Result |
|---|---:|
| Recall on the 71 real pair-level misses | **0/71** |
| False positives on 232 non-contradiction pairs | 0 (after one tightening — see below) |
| Fires correctly on the 175-case dev set's 12 clean number/date/location UNSUPPORTED cases | 12/12 |
| Of those 12, cases where NLI's own raw prediction was *already* "contradict" at 100% confidence | **12/12** |

**Decision: rejected, not wired into the live pipeline.** It works exactly
as designed on clean textbook patterns, but on both real benchmarks tested it
never once activates on a case NLI actually gets wrong — either the case is
clean (and NLI already nails it unaided) or it's adversarial (and the
helper's alignment requirements correctly decline to guess). Wiring it in
would add a real cost (an extra spaCy parse pair per non-contradicting
evidence item) for zero measured benefit, which the brief explicitly says to
reject. Module and its 9 tests are kept, unwired, documented, and ready to
reconsider if a future, less-adversarial benchmark or a different NLI model
shows a different pattern. One real false positive was found and fixed
during validation (a temporal-predicate keyword match across two unrelated
events about the same person) — the lexical-overlap alignment gate that
fixed it is now permanent in the module regardless of this decision.

## 5. Temporal results

Covered above — `needs_current_evidence` reuse verified via unit test
(`test_current_claim_is_not_contradicted_by_an_old_year`); not separately
measured on a benchmark since the helper itself was rejected.

## 6. Source-diversity results

Two distinct, complementary fixes, both validated:

1. **Aggregation-level fix (unconditional, not a toggle):** Group 1's
   duplicate-domain discount had no cap — a domain could repeat itself
   indefinitely, each repetition adding 0.35× more weight, letting volume
   from one non-independent domain out-vote a single genuinely independent
   contradicting source. A purpose-built probe (`probe-diversity-002`, a
   3× syndicated "support" domain vs. one regulatory-filing contradiction)
   caught this producing a **confident wrong verdict** (SUPPORTED). Capped
   at one discounted bonus passage per domain+stance; third+ repeats get no
   further credit. Same probe now returns MIXED_EVIDENCE — the confident
   error is gone. This same fix is very likely why the 175-case replay's
   confident-error count independently dropped 3→2 in this pass (traced to
   `final-scifact-129` flipping from a wrong MIXED_EVIDENCE to the correct
   UNSUPPORTED).
2. **Candidate-pool cap (`max_candidates_per_domain=3`, new setting):** caps
   how many passages from one registrable domain can even reach similarity
   ranking, before NLI. Structurally a no-op on the 175-case dev set (it
   caps at ≤2 sources/case by design) and, honestly, **not shown to move any
   exact verdict on the 5-probe set either** — none of the probes had enough
   same-domain volume to hit the cap before `max_sources` or `top_k` already
   admitted everything. Kept anyway: it is zero-cost on every benchmark
   available, directly targets a documented aggregation-volume risk, and the
   real-world case it protects against (a popular domain returning many
   pages for one query) is exactly the shape `probe-diversity-001/002`
   describe even though those didn't happen to need the pool-level cap
   specifically. Flagged honestly as **not independently proven to move
   accuracy on available data** — a candidate for removal if a future,
   larger benchmark also shows no effect.

## 7. Retrieval-depth results

Root-caused, not guessed: `probe-depth-001` (one clearly on-topic passage
buried among 10 generic-but-topically-similar filler passages, in raw
search-result order) was dropped entirely — not a similarity-ranking
failure (the correct passage actually scored highest, 0.824, once it *was*
considered) but a **`max_sources=10` fetch-order truncation**: the correct
URL was 11th in raw search order and never got fetched. Swept `max_sources`
10/15/20 directly against this probe:

| `max_sources` | Verdict | Correct? |
|---:|---|:---:|
| 10 | INSUFFICIENT_EVIDENCE | ✗ |
| 15 | SUPPORTED | ✓ |
| 20 | SUPPORTED | ✓ (no further gain) |

Raised the default to 15. Confirmed zero regression on the 175-case dev set
(each case has ≤2 fixture sources, so this is a no-op there) and the probe
set gained one correct case with no new confident errors. `top_k` (10) was
left unchanged — nothing in the diagnosis pointed at ranking-window size, and
changing an unimplicated setting would not be a validated change.

## 8. Follow-up-search results

Implemented (`search.follow_up_query`, deterministic, entity/number/date-
weighted via spaCy, no LLM): when the first pass finds literally zero
directional evidence (not merely a low-confidence abstention — a genuine
retrieval gap), one additional targeted query is issued and merged.
`probe-followup-001` (a claim only answered by a specific clinical-trial
registry page, invisible to the claim's own wording) confirms the mechanism
works end-to-end: the follow-up query correctly retrieves the missing page
(`n_evidence` 1 → 2). **Honest limit:** the final verdict on that probe stays
`INSUFFICIENT_EVIDENCE`, not because retrieval failed a second time, but
because NLI classifies the newly-found passage as neutral at 0.57 confidence
(below the 0.65 gate) — a separate, already-known NLI-calibration limitation,
not a Group 2 retrieval defect. **Validation limitation, stated plainly:**
the 175-case dev set's fixture search ignores query text entirely (it always
returns every source regardless of query), so it cannot demonstrate this
mechanism's effect at all — it was validated only via the purpose-built,
query-aware probe set (5 cases), not a large benchmark. A real accuracy
measurement needs either live-web data or an expanded benchmark (deferred;
see Group 3/Phase 16-20 discussion below).

## 9. Ablation table

Measured on the 5-case retrieval probe set (the only available benchmark
that can show these effects at all — see limitation notes above) plus the
175-case regression check:

| Configuration | Probes correct | Probes confident-wrong | 175-case regression? |
|---|---:|---:|---|
| A: Group 1 + capped duplicate-domain credit only (no pool cap / depth / follow-up) | 1/5 | 0 | — (baseline) |
| B: + source-diversity pool cap | 1/5 | 0 | none |
| C: + increased `max_sources` (10→15) | **2/5** | 0 | none, +1 correct |
| D: + follow-up search | 1/5 (mechanism confirmed working; blocked downstream by NLI confidence) | 0 | none |
| E: + structured contradiction helpers | *(rejected before ablation — see §3-4)* | — | — |
| **F: all Group 2 changes combined** | **2/5** | **0** | **net improvement** (see §10) |

**Kept:** capped duplicate-domain credit (real confident-error fix, proven on
both benchmarks), increased `max_sources` (proven root-cause fix), follow-up
search (mechanism proven, benefit currently bounded by NLI, not by
retrieval). **Kept but not proven by available data:** the candidate-pool
diversity cap (zero-cost, theoretically sound, no measured accuracy delta).
**Rejected:** structured contradiction helpers (zero measured benefit on two
real benchmarks, real latency cost — removed from the live path).

## 10. Final Group 2 metrics (175-case controlled replay)

| Metric | Group 1 | Group 2 | Δ |
|---|---:|---:|---:|
| Verdict accuracy | 68.0% | **68.6%** | +0.6pp |
| Coverage | 52.6% | 52.6% | 0 |
| Selective accuracy | 96.7% | **97.8%** | +1.1pp |
| Abstention rate | 47.4% | 47.4% | 0 |
| False abstentions | 53 | 53 | 0 |
| Confident errors | 3 | **2** | −1 |
| Easy accuracy | 90.0% | 90.0% | 0 |
| Medium accuracy | 93.3% | 93.3% | 0 |
| Hard accuracy | 36.0% | **37.3%** | +1.3pp |

## 11-15. False abstentions / confident errors / contradiction metrics

False abstentions: 53 (unchanged from Group 1 — expected, since the fixture
dev set structurally cannot exercise the retrieval-depth/diversity/follow-up
mechanisms that Group 2 actually changed; those only move real, richer
retrieval scenarios, validated separately via the probe set, §7-8).
Confident errors: 2 (down from 3, real fix, see §6). Contradiction
precision/recall/false-contradiction-rate on the NLI holdout are **unchanged**
from Group 1's reported final numbers (75.0% / 38.8% / 6.5%) — nothing in
Group 2 touched the NLI model, its confidence gates, or the pairwise
evaluation, and the one component that could have (structured helpers) was
rejected before being wired in.

## 16. Easy / 17. Medium / 18. Hard accuracy

Easy 90.0% (unchanged), Medium 93.3% (unchanged), Hard 37.3% (+1.3pp from
Group 1's 36.0%). **Group 2's interim hard-accuracy target (≥50%) is not
met.** This is expected and consistent with the contradiction miss analysis
(§2): the largest hard-case failure mode (38% confidently-wrong-direction
NLI predictions, plus genuinely adversarial phrasing) was diagnosed but the
one lever built against it (structured helpers) measured zero benefit and
was rejected. Closing this gap needs either a different NLI model/ensemble
or genuinely different reasoning architecture (iterative evidence
gathering, Phase 18) — out of Group 2's scope as defined.

## 19. Latency impact

Not separately re-measured in wall-clock terms this pass (the fixture replay
has no real network latency to measure). Structurally: `max_sources` 10→15
adds up to 5 more real HTTP fetch+parse calls per atomic claim in live usage
(collect_evidence is sequential, not parallelized) — a real, un-measured
latency cost that should be checked against the live-web latency figures
before Group 4's final run. Follow-up search adds at most one additional
full retrieval pass, but **only** when the first pass found zero usable
evidence (i.e., cases already heading toward the slow "search harder"
path, not the common case). The rejected structured-helper module's latency
cost (extra spaCy parses) does not apply, since it was never wired in.

## 20. Test totals

167 backend tests passed (154 after Group 1 + 13 new: 9
`test_structured_contradiction.py`, 4 `test_hyper_group2.py`), 0 skipped
beyond the pre-existing `RUN_LOCAL_NLI_TESTS` gate. One pre-existing test
(`test_decomposition_attribution.py::test_pipeline_does_not_classify_an_invented_reporting_actor`)
needed a real update — its `collect_evidence` mock assumed exactly one call;
Group 2's follow-up search legitimately calls it twice when no evidence is
found, so the mock was updated to return nothing on the second call (the
realistic case here — there was no more evidence to find), preserving the
test's actual intent (no invented attribution). Backend lint (ruff, `api`
and `evaluation`, matching the project's own CI scope) and format: clean.
Frontend TypeScript: clean (three new optional `Evidence` fields threaded
through, `structured_signal` included though currently unused server-side).
Full Playwright/browser/extension/build suite was **not** re-run this pass
(no frontend rendering logic changed); recommend running it before Group 4's
final lock.

## 21. Regressions

None on the 175-case dev set (every metric held or improved — see §10). One
new-behavior interaction with an existing test's mock, fixed (§20), not a
functional regression. Both retrieval probes that didn't hit their exact
expected label (`probe-diversity-001/002`) moved from "no signal" /
"confident wrong" toward `MIXED_EVIDENCE` — an honest, defensible response to
genuine multi-source conflict, not a regression, though not the ideal
"authoritative single source wins" outcome either; noted as an open design
question (see §22).

## 22. Changes rejected and why

- **Structured contradiction helpers** (§3-4): built, tested, measured zero
  benefit on both the NLI-pair holdout and the controlled dev set, real
  latency cost. Rejected, unwired, kept as documented/tested code.
- **Trusting an unbounded per-domain duplicate discount** (Group 1's
  original formula): superseded mid-Group-2 after a probe exposed a
  confident-error risk; replaced with a capped version (§6). Not a Group 2
  "phase" per se, but a real defect found and fixed along the way.
- **Not addressed, left open rather than force-fixed:** the volume-vs-
  authority tension exposed by `probe-diversity-001/002` (many non-
  independent corroborating mentions vs. one authoritative contradiction) —
  the capped-discount fix removed the *confident-error* risk but the system
  still lands on `MIXED_EVIDENCE` rather than confidently siding with the
  single authoritative source. Fixing this properly would mean weighting
  source *authority* against source *count* explicitly, which risks
  reopening Group 1's validated aggregation formula without a large enough
  benchmark to validate the change safely. Left for Group 3/4 with a real
  benchmark, per the regression-protection instruction to only change
  Group 1 behavior when Group 2 evidence clearly proves a regression --
  this is a real limitation, not a regression.
