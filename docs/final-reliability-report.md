# Final reliability report — READY status: NOT READY

Updated 14 September 2026. This report covers the completed, locked final
evaluation run: the 348-pair NLI holdout, both 175-case controlled-investigation
runs (frozen Pass 2 and the candidate), the 50-case modal batch, all 25 public
URLs, and all 60 live-web claims, followed by the full software verification
suite. All numbers below are from that single locked run. Nothing was retried
selectively, relabeled, or excluded after seeing results.

## 1–3. Frozen baseline, final version, and evaluation lock

- Pass 2 frozen snapshot: `evaluation/final/baseline/pass2-source.tar.gz`,
  sha256 `62653886370423bf1c44f6493876d0ffa4612246d584f03f423a995e31e54bf4`
  (unchanged throughout this pass).
- Final candidate lock: `evaluation/final/lock.json`, sha256
  `dcb01c99687b6f3582aa5be7fa40cce85b3f0b5ccbe908b6136d3a7a10e37771`.
  This is the *third* lock of the session — see [§40, Harness fixes](#40-harness-fixes-applied-during-this-pass)
  for why, and why each re-lock changed exactly one file.
- Only production change versus Pass 2: `api/app/services/propositions.py`
  (preserves embedded/temporal attribution during claim decomposition — see
  the original engineering summary preserved below in §34).
- Models (unchanged from Pass 2): NLI
  `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` (revision `6f5cf0a2b5...`),
  embeddings `sentence-transformers/all-MiniLM-L6-v2`, proposition relevance
  `cross-encoder/ms-marco-MiniLM-L6-v2`. Key packages: torch 2.14.0,
  transformers 4.57.6, sentence-transformers 5.7.0, spacy 3.8.16,
  trafilatura 2.2.0, rapidocr-onnxruntime 1.4.4.

## 4–5. Dataset sizes and split methodology

- NLI: 648 balanced pairs (180 development / 120 validation / 348 held-out
  test), 216 per class overall; sourced from 600 ANLI pairs plus 48 authored
  probes across 16 domains. All paraphrase/variant groups stay within one
  split. A prior audit against 800 historical unique claims found no exact
  claim or split-group overlap (does not establish absence of semantic overlap
  or pretraining contamination).
- Controlled investigations: 175 held-out (40 easy / 60 medium / 75 hard):
  100 authored factual cases, 50 human-labelled SciFact-dev cases, 25 authored
  stress scenarios. Fixture URLs are controlled test documents, not live
  citations; SciFact evidence is supplied cited abstracts, not open-web
  discovery; authored labels lack independent review; difficulty strata are
  constructed, not independently calibrated.
- Product workflow: 50 typed/pasted + OCR modal cases (20 cases × up to 3
  routes), 25 fixed public URLs, 60 live claims (20 per difficulty).

## 6. Final NLI results (348-pair held-out test set)

Three readings of the same run, since a prior internal helper conflated them
(see handoff): **predicted** is confidence-gated — what production actually
outputs, including abstention below the 0.65/0.85 thresholds. **winning** is
the model's raw top label with no gating. Production behavior is **predicted**.

| | Accuracy | Macro F1 | False contradiction rate |
|---|---:|---:|---:|
| predicted (production-gated) | 56.6% | 0.560 | 6.5% |
| winning (ungated top label) | 60.6% | 0.604 | 15.9% |
| raw (legacy ambiguous reading, kept for continuity) | 60.1% | 0.599 | 13.8% |

Per-label (production-gated, **predicted**):

| Label | Precision | Recall | F1 |
|---|---:|---:|---:|
| Support | 63.6% | 54.3% | 0.586 |
| Contradict | 75.0% | 38.8% | 0.511 |
| Neutral | 47.1% | 76.7% | 0.584 |

This is a real, run-once, locked measurement — not the earlier 120-pair
*validation* set reported during development (macro F1 0.573), and not
directly comparable to it.

## 7–13. Verdict accuracy, coverage, selective accuracy, abstention, contradiction metrics

These come from the 175-case controlled-investigation run. **Pass 2 (frozen)
and the candidate produced byte-identical predictions on all 175 cases** — see
§38 for why. Figures below apply to both.

| Metric | Value | Target | Met? |
|---|---:|---:|:---:|
| Verdict accuracy | 44.6% (78/175) | ≥90% | ✗ |
| Coverage (non-abstaining) | 28.6% | ≥80% | ✗ |
| Selective accuracy (correct \| committed) | 96.0% | ≥92% | ✓ |
| Abstention rate | 71.4% | — | — |
| Correct abstentions | 30 | — | — |
| False abstentions (should have committed) | 95 | — | — |
| Confident errors (committed and wrong) | 2 | — | — |

Contradiction metrics are the NLI-holdout figures in §6 (production-gated):
precision 75.0% (target ≥92%, ✗), recall 38.8% (target ≥80%, ✗), F1 0.511,
false contradiction rate 6.5% (target ≤2%, ✗).

## 14–17. Support / neutral metrics, NLI macro F1

Covered in §6 above (production-gated per-label table). NLI macro F1 0.560
against a target of ≥0.88 — not met.

## 18. Retrieval metrics (Recall@5 / Recall@10)

**Not measured in this run.** The prepared runner does not compute retrieval
recall against a labelled relevant-passage set for the final controlled/live
cases; only downstream verdict outcomes are recorded. This is a gap, not a
zero result — do not read "not measured" as "0%."

## 19–21. Accuracy by difficulty

| Difficulty | Count | Correct | Accuracy | Coverage | Selective accuracy | Target | Met? |
|---|---:|---:|---:|---:|---:|---:|:---:|
| Easy | 40 | 23 | 57.5% | 57.5% | 100% | ≥95% | ✗ |
| Medium | 60 | 36 | 60.0% | 35.0% | 100% | ≥90% | ✗ |
| Hard | 75 | 19 | 25.3% | 8.0% | 66.7% | ≥75% | ✗ |

By origin: authored-controlled (n=125) 54.4% accuracy, 39.2% coverage, 98.0%
selective accuracy; SciFact-dev (n=50) 20.0% accuracy, 2.0% coverage, 0%
selective accuracy (the one case it committed on was wrong).

## 22. Typed claim results

Modal-stage typed/pasted "text" route: **20/20 completed (100%)**, latency
median 1.9s / p95 2.3s. Separately, the controlled/baseline run's 50
browser-typed cases: median 1.6s / p95 2.1s (fixture search, no real network —
not comparable to live latency).

## 23. Public URL results

**15/25 completed (60%)**, target ≥95%, not met. Latency (completed only):
median 28.5s / p95 119.8s across all 25 attempts (median 39.7s / p95 105.7s
restricted to the 15 completions). 10 failures, all against **real, live
external websites** (not a fixture defect):

| URL | Failure mode |
|---|---|
| nasa.gov (Mercury facts) | Extraction failed |
| noaa.gov (climate resource) | Extraction failed |
| bls.gov (CPI Q&A) | Extraction failed |
| ox.ac.uk (history page) | Extraction failed |
| cam.ac.uk (history page) | Extraction failed |
| news.stanford.edu (carbon capture) | Extraction failed |
| apnews.com (science hub) | Extraction failed |
| reuters.com (sustainability hub) | Extraction failed |
| mit.edu (about page) | Timeout (150s), no response |
| bbc.com (science/environment article) | Timeout (150s) on submit |

8 are extraction failures (site likely blocks scraping, requires JS rendering,
or the page structure defeated `trafilatura`); 2 are genuine slow/unresponsive
interactions. These are real product-level limitations on real websites, not
harness artifacts — unlike the modal-stage failures below.

## 24. Pasted article results

Covered by "typed claim results" above (§22) — the modal "text" route mixes
typed and pasted-article submission; **100% completion (20/20)**, meeting its
≥95% target.

## 25. OCR results

**No usable data was collected.** All 20 image-route modal cases failed with
the same Playwright timing defect (see §40); this happened *before* the point
in the test script where OCR extraction is captured, so `ocr-observations.jsonl`
is empty. This is a harness gap, not evidence that OCR itself is broken — the
separate backend OCR regression test (part of the software suite, §33) passed.
**OCR quality (CER/WER) and corrected-text propagation remain unverified at
final scale.**

## 26. Cross-modal consistency

10 cases probed across up to 4 signatures (typed/modal-text, the matching
controlled-run result, image, url). Only 2 of the 4 routes ever completed
(image and url both failed for the harness reason above), so every case is
marked incomplete (`consistent: 0/10` against a target of ≥10). Of the two
routes that *did* complete, all 10 agreed with each other on both claim
normalization and verdict. **Conclusion: no evidence of cross-modal
disagreement was found, but the test could not exercise 2 of its 4 intended
modes, so this does not establish full cross-modal consistency.**

## 27. Compound claims

Not part of this final run — see limitations (§35): the 50 compound-sentence
probes are development-only material (33/50 → 36/50 authored-string agreement
after the propositions.py fix), not a held-out final measurement.

## 28–30. Numerical, temporal, and source-conflict cases

Present among the 175 controlled investigations' hard-difficulty tags
(`units`, `nominal-real`, `before`, `after`, `temporal-role`,
`measurement-conflict`, `source-conflict`, `statistic-conflict`) but not
broken out as a separate metric by the runner. See §36 for the specific
failing cases by tag.

## 31. Live-web observations

**Not accuracy — no independent gold labels exist for these.** 60/60 claims
completed (100% workflow completion), 20 per difficulty tier.

| Verdict | Count |
|---|---:|
| SUPPORTED | 19 |
| UNSUPPORTED | 22 |
| INSUFFICIENT_EVIDENCE | 16 |
| MIXED_EVIDENCE | 3 |

Latency: median 22.5s / p95 32.6s. No search failures, extraction failures, or
workflow crashes were recorded for this batch. **Whether these 60 verdicts are
individually correct has not been checked against independent ground truth —
do not read 100% completion as 100% accuracy.**

## 32. Latency summary (all stages, this run)

| Stage | n | Median | p95 | Note |
|---|---:|---:|---:|---|
| Controlled (candidate) | 175 | 1.35s | 2.06s | Fixture search — not representative of live latency |
| Controlled (Pass 2 baseline) | 175 | 1.36s | 2.06s | Same |
| Modal (typed/image/url mixed) | 50 | 1.87s | 2.31s | Only the 20 completed text-route cases have real timing |
| Public URLs | 25 | 28.5s | 119.8s | Real network + real page rendering |
| Live-web claims | 60 | 22.5s | 32.6s | Real search + real fetch |

Resource use (peak RSS, CPU float64 workaround, etc.) was not separately
aggregated by the runner in this pass.

## 33. Automated test totals

Unaffected by this evaluation pass — no production source (`api/app`, `web/`,
`extension/`) changed; only the evaluation harness (`evaluation/final/`) was
touched (see §40), so these results, generated earlier the same day, stand:

| Suite | Result |
|---|---|
| Backend (pytest, real Postgres + real local NLI) | 138 passed, 3 warnings |
| Frontend (vitest) | 13 passed |
| Browser (Playwright, Chromium + WebKit) | 14 passed (5.7 min) |
| Extension | 2 passed |
| Production build | Passed |
| TypeScript | Passed |
| Backend lint (ruff) | All checks passed |
| Backend format | 86 files already formatted |
| Frontend lint (eslint) | Passed |
| Frontend format (prettier) | All matched files use Prettier style |

## 34. Failure analysis

At the individual-evidence level (why a genuine contradiction was missed,
across all NLI evaluation in this run):

| Cause | Count |
|---|---:|
| NLI prediction (model called it wrong) | 57 |
| Relevance filter excluded the evidence | 8 |
| NLI confidence below threshold | 5 |
| Temporal/context filter | 1 |

At the investigation-verdict level (why a controlled-run verdict was wrong,
97 errors across all 175 cases, principled categorization computed by the
locked runner itself, not chosen after seeing results):

| Root cause | All errors (n=97) | Hard-only (n=56) |
|---|---:|---:|
| Aggregation / source weight / atomic coverage (system had evidence with a stance but aggregation rules chose to abstain) | 67 (69%) | 27 (48%) |
| Eligibility filters (relevant evidence was excluded before NLI) | 26 (27%) | 25 (45%) |
| NLI prediction or confidence (model itself wrong on retained evidence) | 2 (2%) | 2 (4%) |
| Retained evidence relation / source conflict | 2 (2%) | 2 (4%) |

**These two tables measure different things and are not in tension**: most
individual missed *contradictions* are genuine NLI model errors, but most
final *wrong verdicts* come from the aggregation/eligibility layer being too
conservative and abstaining rather than committing incorrectly. This matches
the 96% selective accuracy / 28.6% coverage picture — the system is
usually right when it commits, but commits far too rarely.

## 35. Remaining limitations

- OCR quality at final scale is unverified (harness gap, §25).
- Cross-modal consistency is only partially exercised (2 of 4 routes, §26).
- Retrieval Recall@5/10 was not measured (§18).
- Compound-claim, numerical, and temporal performance were not isolated as
  distinct final metrics (§27–29).
- SciFact-dev cases use supplied abstracts, not open-web discovery.
- Authored gold labels are not independently reviewed.
- Difficulty strata are constructed, not independently calibrated.
- Public-URL and live-web samples (25 and 60 respectively) are small; observed
  failure/verdict rates carry wide uncertainty.
- No exact-frame numeric override exists (none was validated as beneficial in
  development); no broader structured-check validation has occurred.

## 36. Most serious remaining weakness, with concrete failures the system gets wrong

**The dominant weakness is coverage, not the NLI model per se**: the system
abstains (`INSUFFICIENT_EVIDENCE`) on 71% of held-out controlled claims,
including 95 cases where a confident, correct verdict was actually available —
far more than the 30 cases where abstention was the right call. This is most
severe on hard cases (92% abstention rate, only 8% coverage) and on SciFact
(98% abstention, 2% coverage). Contradiction recall (38.8%) is the weakest
single NLI metric — the system misses roughly 6 in 10 genuine contradictions
in the holdout, overwhelmingly (57/71 misses) because the NLI model itself
does not call them "contradict," not because of upstream filtering.

Concrete examples the system still gets wrong (full list in
`evaluation/final/results/investigation-errors.json`; two representative
confident — non-abstaining — errors, both hard):

- `final-hard-013` (entity-collision, geography): expected
  `INSUFFICIENT_EVIDENCE`, predicted `MIXED_EVIDENCE`.
- `final-scifact-129` (expert-scientific, health/science): expected
  `UNSUPPORTED`, predicted `MIXED_EVIDENCE`.

Representative *false-abstention* failures (should have committed but didn't):
`final-hard-002` (two-actors, space; expected SUPPORTED), `final-hard-006`
(before, history; expected SUPPORTED), `final-hard-007` (after, transportation;
expected SUPPORTED), and the large majority of SciFact-dev cases where a
labelled SUPPORTED/UNSUPPORTED claim was abstained on instead.

## 37. See §36.

## 38. Pass 2 vs Final comparison

**On this specific final benchmark, Pass 2 (frozen) and the candidate produced
identical results on all 175 controlled investigations and on the (single,
shared) NLI holdout** — because the only code difference between them,
`propositions.py`'s decomposition fix, is not exercised by any claim in this
benchmark (none of the 175 held-out claims contain the embedded-attribution
compound-sentence pattern the fix targets; the NLI holdout doesn't involve
decomposition at all). This is a real, verified null result, not a
measurement artifact — every one of the 175 `predicted` fields matched
byte-for-byte between the two runs.

| Metric | Pass 2 (this benchmark) | Final (this benchmark) |
|---|---:|---:|
| Verdict accuracy | 44.6% | 44.6% |
| Coverage | 28.6% | 28.6% |
| Selective accuracy | 96.0% | 96.0% |
| Abstention rate | 71.4% | 71.4% |
| Easy / medium / hard accuracy | 57.5% / 60.0% / 25.3% | 57.5% / 60.0% / 25.3% |
| NLI macro F1 (production-gated) | 0.560 | 0.560 |
| Contradiction precision / recall | 75.0% / 38.8% | 75.0% / 38.8% |
| False contradiction rate | 6.5% | 6.5% |

For reference only — **not directly comparable**, different and much smaller
(31-case) holdout, measured during earlier development, cited here only so it
isn't mistaken for a regression: Pass 2 historically scored 87.1% verdict
accuracy, 77.4% coverage, 91.7% selective accuracy, 87.5%/56.8% contradiction
precision/recall, 4.1% false contradiction rate on its own prior benchmark.
The gap between that figure and the 44.6%/28.6% figure above is a difference
in *benchmark difficulty and size*, not a regression introduced this pass —
Pass 2's frozen code scores identically to the candidate on the new benchmark.

The production fix did demonstrably work — six new unit regressions
(`test_decomposition_attribution.py`) and a development-only compound-sentence
improvement (33/50 → 36/50 authored-string agreement) confirm it — it simply
isn't exercised by this particular held-out set.

## 39. Final readiness decision

# NOT READY

This is the decision the locked runner itself computed against 14
pre-committed targets fixed before the run (`evaluation/final/summarize.py`),
not a judgment made after seeing the numbers:

| Target | Threshold | Actual | Met? |
|---|---|---:|:---:|
| NLI macro F1 | ≥0.88 | 0.560 | ✗ |
| Contradiction precision | ≥0.92 | 75.0% | ✗ |
| Contradiction recall | ≥0.80 | 38.8% | ✗ |
| False contradiction rate | ≤0.02 | 6.5% | ✗ |
| Overall accuracy | ≥0.90 | 44.6% | ✗ |
| Coverage | ≥0.80 | 28.6% | ✗ |
| Selective accuracy | ≥0.92 | 96.0% | ✓ |
| Cross-modal consistency | ≥10 complete & consistent | 0 | ✗ |
| Public URL completion | ≥0.95 | 60.0% | ✗ |
| Pasted-article completion | ≥0.95 | 100% | ✓ |
| OCR completion | ≥0.90 | 0% | ✗ |
| Easy accuracy | ≥0.95 | 57.5% | ✗ |
| Medium accuracy | ≥0.90 | 60.0% | ✗ |
| Hard accuracy | ≥0.75 | 25.3% | ✗ |

2 of 14 targets met. The system is precise when it commits (96% selective
accuracy) but commits far too rarely (28.6% coverage), and two workflow paths
(public URL, OCR) fall well short of completion targets — OCR's shortfall is
substantially a harness measurement gap (§25) rather than a demonstrated
product defect, but it remains unverified either way.

## 40. Harness fixes applied during this pass

Two defects in the evaluation harness itself (`evaluation/final/`, not the
product) were found and fixed during this run, each with explicit
authorization, each re-locked, each verified to touch exactly one file:

1. `application.py`'s `/evaluation/trace` endpoint never returned `variant`/
   `stage`, which `product.mjs` asserts on at startup — this blocked every
   product-evaluation mode before it could run a single case. Fixed by
   returning the already-computed module-level `variant`/`stage` values.
   Re-lock sha256 `d98bd0890a4f346c9b98569670af3d9ce049018b42071f396c2c010919022763`
   (superseded by fix 2 below).
2. Four `page.waitForResponse(...)` call sites in `product.mjs` created their
   wait-promise before the triggering click and only awaited it afterward; a
   slow response could reject before that `await` was reached, crashing the
   whole Node process as an unhandled rejection instead of being caught by
   `attempt()`'s existing try/catch (which correctly recorded 7 other URL
   failures). This halted the run mid-way through the public-URL stage,
   before any of the 60 live claims ran. Fixed with an immediate no-op
   `.catch(() => {})` on each wait-promise; the real result/error still flows
   through the original `await` into the unchanged error handling. Final lock
   sha256 `dcb01c99687b6f3582aa5be7fa40cce85b3f0b5ccbe908b6136d3a7a10e37771`.

Both fixes are mechanical, non-reasoning changes to test-harness robustness —
neither touches `api/app`, `web/`, `extension/`, models, thresholds, prompts,
decomposition logic, source weighting, contradiction rules, or benchmark
labels. Each re-lock diff was verified to change exactly one `files` hash
entry (plus the unavoidable `archive_sha256`/`created_at` fields). Full
narrative and both preceding lock snapshots are in `evaluation/final/STATUS.md`
and `evaluation/final/results/lock-before-*.json`. No case outcome, label, or
result was altered, retried selectively, or removed as part of either fix —
the run was resumed via the existing per-case journal, not redone, so every
already-completed result (NLI holdout, both 175-case controlled runs, modal)
is exactly as first produced.

## 41. Defensible CV wording / what not to claim

**Defensible:**
- "Built an end-to-end fact-verification pipeline (claim decomposition,
  retrieval, NLI-based evidence scoring, abstention-aware aggregation) with a
  locked, reproducible final evaluation protocol (hash-verified source,
  models, and data) covering 348 held-out NLI pairs, 175 held-out
  investigations, 25 real public URLs, and 60 live web claims."
- "Diagnosed and fixed two concurrency/robustness defects in a custom
  browser-automation test harness, each isolated from and independently
  re-locked against the production system under test."
- "Selective accuracy of 96% when the system commits to a verdict, with an
  explicit, measured abstention mechanism, across a 175-case held-out
  benchmark."
- "Identified, via a principled per-error root-cause classification, that the
  dominant failure mode is conservative aggregation causing under-coverage
  (71% abstention) rather than confident incorrect verdicts (96% selective
  accuracy)."

**Do not claim:**
- "90%+ accuracy" or any specific accuracy figure without stating it's 44.6%
  overall / 28.6% coverage on the locked final benchmark — the true, complete
  figures, not the older 87.1%/different-and-smaller-holdout number.
- "Cross-modal consistency verified" — only 2 of 4 intended modes completed.
  Say "no disagreement observed in the 2 of 4 modes that completed."
  Do not describe this as full or held-out completion.
- "OCR accuracy" or "OCR completion rate" of any kind — no OCR data was
  collected in this run.
- Any live-web claim about accuracy — 60/60 is *workflow completion*, not
  verified correctness.
- That software test totals (138/13/14/2 passing, build/lint/format clean)
  constitute or substitute for factual reliability.
- That this evaluation is "production-validated" or "release-ready" — the
  locked runner's own decision is **NOT READY**.

---

Prior engineering summary (unchanged, preserved for continuity):

The only production change relative to frozen Pass 2 is in
`api/app/services/propositions.py`. The previous splitter could turn "The
journalist said the company expanded and hired workers" into "The journalist
hired workers." Embedded complements and ambiguous before/after scope now
remain intact, and conjunctions must belong to the main coordination. This
deliberately preserves attribution rather than inventing an actor; it does not
solve general compound-claim decomposition. Six regressions cover embedded
statements, temporal scope, an ordinary direct conjunction, and the actual
investigation pipeline's NLI arguments. The OCR frontend regression verifies
corrected text in both proposal and investigation requests; the browser
regression verifies the same payload. No OCR product change was needed.
