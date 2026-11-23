# Claim Check — Hyper Final Reliability Report (Group 4)

This report answers one question: **do the Group 1–3 reasoning changes
generalize to claims, evidence, and product inputs the system has never
seen tuned against?** Groups 1–3 improved the system against a 175-case
development benchmark and a 348→2400-pair development NLI pool. Those
numbers are development-replay metrics, not held-out evidence of
reliability. Group 4 built an entirely new, independently-audited
evaluation corpus, froze the system before generating any prediction
against it, ran it exactly once, and reports the result — good or bad —
without further tuning.

**Bottom line, stated up front:** the New Hyper Holdout shows the Group
1–3 reasoning improvements substantially generalize on decided-verdict
accuracy, medium accuracy, hard accuracy, and selective accuracy, but not
on coverage, contradiction recall, false-contradiction rate, or any
product-input-modality metric (OCR, URLs, cross-modal). Readiness decision:
**NOT READY** (below).

---

## 1. Architecture (unchanged since Group 1)

FastAPI backend (`api/app`) + Next.js frontend (`web/`) + a browser
extension (`extension/`). Pipeline: claim decomposition (`propositions.py`)
→ query generation → search (Tavily/Brave, `search.py`) → article
extraction (`trafilatura`, `article_extraction.py`) → per-source stance via
a DeBERTa-v3-large NLI cross-encoder (`nli.py`) → graded relevance
weighting + claim-risk-gated aggregation (`evidence_scoring.py`,
`claim_risk.py`) → verdict (`SUPPORTED` / `UNSUPPORTED` / `MIXED_EVIDENCE`
/ `INSUFFICIENT_EVIDENCE`). No architectural change was made in Group 4;
only the frozen Group 1–3 system was evaluated.

## 2. Exact configuration under evaluation

From `evaluation/hyper/final/lock.json`, computed **before** any Group 4
benchmark data or prediction existed (see §7):

| Setting | Value |
|---|---|
| NLI model | `MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli` (rev. `b3546ea6…`) |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Proposition/reranking model | `cross-encoder/ms-marco-MiniLM-L6-v2` |
| `minimum_evidence` | 0.20 |
| `min_contradiction_confidence` | 0.70 |
| `max_sources` | 15 |
| `max_candidates_per_domain` | 3 |
| `duplicate_source_weight` | 0.35 |
| Authority tiebreak | min_weight 0.90, max_opposing_weight 0.75, max_opposing_sources 2 |
| Source weights | research 1.0, official 0.95, institution 0.90, reporting/encyclopedia 0.75, general 0.70, unknown 0.30 |
| High-risk claims | minimum_evidence 0.65, dominance_ratio 2.5, min_independent_sources 2 |
| Relevance | floor 0.0 (hard exclusion), full weight at 4.0 |
| Follow-up search | enabled, max 1 query |
| Key packages | torch 2.14.0, transformers 4.57.6, sentence-transformers 5.7.0, spacy 3.8.16, trafilatura 2.2.0, rapidocr-onnxruntime 1.4.4 |

## 3. Model selection history (Groups 1–3, summary)

Group 1 replaced a hard proposition-relevance cutoff with graded
relevance weighting and added claim-risk-gated evidence requirements.
Group 2 diagnosed contradiction misses at the pair level (45.1% raw-neutral,
38.0% opposite-direction, 16.9% under-confidence-threshold) and ran a
systematic NLI model bake-off; the current DeBERTa-v3-large model won on
every axis (precision, recall, F1, false-contradiction rate) at acceptable
latency/memory cost — see `evaluation/hyper/GROUP2-RESULTS.md` §3–7 for the
full comparison table. Group 3 recalibrated the contradiction-confidence
threshold and `minimum_evidence` against a coverage/selective-accuracy
curve, and added atomic-coverage tracking for compound claims. No further
model/threshold change has been made since; this is the exact system Group
4 evaluated.

## 4. Group 1 results (development replay)

Verdict accuracy 68.0%, coverage 52.6%, selective accuracy 96.7%, false
abstentions 53, confident errors 3, easy/medium/hard 90.0%/93.3%/36.0%.
Full detail: `evaluation/hyper/GROUP1-RESULTS.md`.

## 5. Group 2 results (development replay)

Same verdict metrics as Group 1 (Group 2 was NLI-model-focused, not
aggregation-focused): the headline finding was the pair-level contradiction
miss taxonomy above, plus the model bake-off that selected the current NLI
model. Full detail: `evaluation/hyper/GROUP2-RESULTS.md`.

## 6. Group 3 results (development replay — NOT an independent holdout)

| Metric | Group 1/2 | Group 3 |
|---|---:|---:|
| Verdict accuracy | 68.6% | **76.0%** |
| Coverage | 52.6% | 61.1% |
| Selective accuracy | 97.8% | 97.2% |
| Confident errors | 2 | 3 |
| False abstentions | 53 | 39 |
| Easy accuracy | 90.0% | 90.0% |
| Medium accuracy | 93.3% | 93.3% |
| Hard accuracy | 37.3% | **54.7%** |
| Contradiction precision (validation) | 75.0% | 88.2% |
| Contradiction recall (validation) | 38.8% | 75.0% |
| False contradiction rate (validation) | 6.5% | 5.0% |

**This 76.0% figure is a replay of the same 175 cases used throughout
development, and the "validation" NLI split it partly draws contradiction
P/R from is itself development data used to pick the threshold. It has
never been an independently held-out number and must not be reported as
one.** Full detail: `evaluation/hyper/GROUP3-RESULTS.md`.

## 7. New benchmark construction (Group 4, Phases 1–3)

**Phase 1 — freeze first.** `evaluation/hyper/final/freeze.py` hashed the
entire production system (`api/app`, `api/tests`, `api/migrations`,
`web/app`, `web/components`, `web/lib`, `web/tests`, `web/e2e`,
`extension/`) plus resolved configuration, model revisions, and package
versions **before** any Group 4 benchmark file existed
(`results/lock-phase1-system-freeze.json`, sha256
`356d02ba1e3535f89d4e9d815258ef76edd680ba53527861070bd9410470ce10`).

**Phase 2 — new NLI holdout.** 804 pairs (min. 600 required): 720 freshly
mined from the unused two-thirds of the 2400-pair ANLI source pool (only
600 of 2400 pairs had ever been consumed by prior work), hash-deduplicated
against every prior corpus in the repo, plus 84 hand-authored pairs across
28 explicit categories (paraphrase, negation, dates, numbers, percentages,
money, locations, entity relationships, causation, rankings, comparisons,
historical-vs-current, lexical-overlap traps, same-topic/different-predicate
neutrals, partial entailment, long/noisy evidence, similar named entities,
and 8 domain categories: science/business/sports/history/geography/
technology/medicine/environment-culture-space). Split: 180 development /
188 validation / 436 test (356 of the 436 test-split pairs are ANLI-mined
and were never touched during construction beyond the leakage audit — well
above the 300-case minimum). Balanced 268/268/268 across
support/contradict/neutral.

**Phase 3 — new end-to-end benchmark.** 250 controlled investigations (≥250
required): 60 easy / 90 medium / 100 hard. 206 authored (new facts,
alternatives, and hard scenarios spanning 16 domains and 21 hard-case tag
categories — partial truths, contradictory sources, outdated-vs-current
evidence, multi-atom claims, evidence spread across sources, subtle
numerical differences, temporal conflicts, similar entity names,
authority-vs-volume conflicts, causation-vs-correlation, changing
officeholders, statistics with different denominators, genuine
insufficient-evidence cases) + 44 freshly pulled SciFact claims (16
SUPPORTED / 16 UNSUPPORTED / 12 INSUFFICIENT_EVIDENCE), excluding every
document/claim ID used by the old `evaluation/final` SciFact pull. Verdict
distribution: SUPPORTED 95, UNSUPPORTED 98, INSUFFICIENT_EVIDENCE 47,
MIXED_EVIDENCE 10 — all four classes represented without severe imbalance.

## 8. Independence / leakage audit (Phase 4)

Two automated audits (`build_and_audit_nli.py`, `audit_investigations.py`),
documented in full in `evaluation/hyper/final/LEAKAGE-AUDIT.md`:

| Check | NLI holdout (804 pairs) | Investigations (250 cases) |
|---|---:|---:|
| Prior texts scanned | 5,047 | 5,047 |
| Exact hash overlap | 0 | 0 |
| Near-duplicate (≥85–90% word Jaccard) | 0 | 0 |
| Internal duplicates | 0 | 0 |

Two real exact-text collisions were found and fixed during construction
("A byte consists of eight bits." and "Jane Austen wrote Pride and
Prejudice." both coincidentally appeared in `evaluation/pass2/data/
verdicts.json") — both facts were replaced with different trivia before the
final audit above, which is clean. **Disclosed limitation:** the audit
checks exact and near-exact text overlap only; semantic overlap on
inherently finite general-knowledge topics (e.g., Lake Baikal's depth
appearing, differently phrased, in both an old and new corpus) cannot be
fully ruled out and is not claimed to be.

## 9. Final lock and hash (Phase 1/11)

The system, all Group 4 benchmark data, and the harness that runs it were
locked together before any final prediction was generated
(`results/lock-before-experiment-py-fix.json`, sha256
`0774b6b22e9c896bc2beb2e1d836678e628a35aa221e26fcffeebc048f53fb23`) and the
run executed under `results/lock-before-modal-harness-fix.json` (sha256
`76ffbaf5bbcdbc6c3760b8e8a403ffed4f571a7d7cfb20b7573e5e1d8397a0f8`). Two
harness-only repairs were required after that point (§32); the active lock
after both repairs plus a Phase 14 lint/format cleanup is
`evaluation/hyper/final/lock.json`, sha256
`3478e87ccda22bba7997df817f089ceef5a89699294cc1ed1d5587b6090e3156`. The
full, ordered lock chain (9 locks) is preserved under
`evaluation/hyper/final/results/lock-*.json` and documented in
`evaluation/hyper/final/HARNESS-FIXES.md`. **No production file
(`api/app/**`, `web/**`, `extension/**`) differs between the very first
Phase 1 lock and the final active lock, except the one documented
`evaluation/pass2/experiment.py` bug fix (§32).**

## 10. New NLI holdout results (test split, 436 pairs, independently held out)

| Field | Macro F1 | Contradiction P | Contradiction R | False-contradiction rate |
|---|---:|---:|---:|---:|
| Confidence-gated production stance (`predicted`) | 65.5% | 76.1% | 58.1% | 9.4% |
| Raw top NLI label (`winning`, ungated) | 73.6% | — | — | — |

Full per-label precision/recall/F1 and the 3×3 confusion matrix are in
`evaluation/hyper/final/results/summary.json` → `nli.predicted`. Compared
to Group 3's development-replay validation numbers (88.2% precision / 75.0%
recall / 5.0% false-contradiction rate), **every NLI metric is
substantially worse on unseen pairs** — the clearest single sign that
Group 3's threshold tuning overfit its own validation split.

## 11. New end-to-end investigation results (250 cases, independently held out)

Overall verdict accuracy **80.8%** (202/250), coverage **65.2%**, selective
accuracy **95.7%**, confident errors **7**, correct abstentions **46**,
false abstentions **41**.

## 12. Coverage

65.2% (163/250 cases received a decided verdict; 87 abstained as
`INSUFFICIENT_EVIDENCE`) — below the ≥70% pre-committed target, and below
Group 3's development-replay coverage (61.1%, though that number is not
directly comparable since the case mixes differ).

## 13. Selective accuracy

95.7% among decided cases — **above** the ≥92% target, and roughly in line
with every prior generation (96–98% range across Old Final, Group 1–3 dev).
This is the strongest generalizing result in this evaluation: when the
system commits to a verdict, it is very likely right, on both development
and unseen data alike.

## 14. False abstentions

41 of 250 cases (16.4%) — cases with a real, decidable verdict that the
system declined to call. Down in absolute rate from the Old Final locked
run (95/175 = 54.3%), a real generational improvement, but still the
largest single component of the accuracy gap versus the ≥70% coverage
target.

## 15. Confident errors

7 of 163 decided cases (4.3%) — cases where the system committed to a
verdict and got it wrong. Slightly higher in count than Group 3's dev-replay
number (3) but off a larger and independent decided-case pool; as a rate
it is comparable (4.3% vs Group 3's ~1.7-3% depending on denominator) and
not the primary source of inaccuracy — false abstention and undecided
coverage dominate.

## 16. Easy / medium / hard accuracy

| Difficulty | n | Accuracy | Target | Met? |
|---|---:|---:|---:|---|
| Easy | 60 | 91.7% | ≥95% | ✗ (close) |
| Medium | 90 | 94.4% | ≥90% | ✓ |
| Hard | 100 | 62.0% | ≥60% | ✓ |

**Hard-case accuracy holding at 62% on genuinely unseen hard cases —
matching and slightly exceeding the ≥60% target, and consistent with
Group 3's dev-replay hard-accuracy jump (37.3%→54.7%) — is the clearest
evidence that the Group 1 relevance-weighting and claim-risk work
generalizes.** Easy-case accuracy landing at 91.7%, just under target, is
driven partly by the SciFact-origin subset (see §17) rather than the
authored easy facts specifically.

## 17. Accuracy by case origin

| Origin | n | Accuracy |
|---|---:|---:|
| Authored controlled (facts/hard scenarios) | 206 | 86.4% |
| SciFact-dev (fresh scientific claims) | 44 | 54.5% |

Scientific claims drawn from real abstracts are substantially harder for
this system than authored general-knowledge claims — a genuine, previously
under-measured weakness (the old evaluation's SciFact pull was smaller and
not broken out this way).

## 18. Contradiction precision / recall / false-contradiction rate (product-level NLI, §10 repeated for the requested numbering)

76.1% / 58.1% / 9.4% (confidence-gated), vs. pre-committed targets of ≥88%
/ ≥65% / ≤4%. All three missed on the independent holdout, despite Group 3
appearing to clear all three against its own development validation split.

## 19. Typed-claim workflow

30/30 completed (100%), median latency 2.33s, p95 2.89s (browser-automated
typed route). A separate typed-browser sub-sample used for cross-modal
comparison (60 cases) had median 2.56s / p95 3.35s. Both comfortably meet
the pasted-completion-style target.

## 20. Public URL workflow (Phase 7)

**17/30 completed (56.7%)** — below the ≥85% target. 30 new URLs spanning
government, university, science-org, company, news, statistics, long-form,
JS-heavy, and static-page categories, none reused from the prior 25-URL
set. Failures were a mix of explicit Playwright timeouts (real slow/blocked
pages: `faa.gov`, `nsf.gov`, `ourworldindata.org`, `react.dev`,
`britannica.com`, others) and silent extraction failures on pages that
loaded but yielded no usable article text (`epa.gov`, `cdc.gov`,
`jpl.nasa.gov`, `tesla.com`, `apnews.com`, `imf.org`, two Wikipedia pages).
Blocked/failed URLs were kept in the denominator per Phase 7's instruction
— this is a real product-reliability number, not a harness artifact.
Completed-case latency: median 51.7s, p95 118.4s (real network fetch +
extraction + investigation, not a fixture).

## 21. Pasted-article workflow

Covered under §19 (the "text"/pasted route in the modal-stage harness):
30/30 completed (100%), well above the ≥95% target.

## 22. OCR workflow (Phase 6)

**Not measurable this pass, again.** 30 new varied OCR images were
generated (clean/small-text/dark/light background/JPEG compression/
blur/narrow-wrapped/multi-paragraph/with-and-without digits), but every one
of the 30 browser-automated attempts failed with `Protocol error
(Network.getResponseBody): Request content was evicted from inspector
cache)` — a Playwright/CDP response-body timing bug. A reasoning-neutral
harness fix was attempted (reading the response body synchronously inside
an immediate `page.on("response")` handler instead of deferring `.json()`
until after the click) and did **not** resolve it; all 30 still fail
identically. This means CER/WER, proposal-success, corrected-text
propagation, and investigation-completion could not be measured through
this harness for the third pass running. Per the explicit Group 4
instruction, production OCR code was **not** altered to route around this.
Separately, the backend's own OCR unit/regression tests (which call the OCR
function directly, no browser automation) continue to pass and are
unaffected by this specific bug — see §33.

## 23. Cross-modal consistency

**0/20 consistent (0%)**, against a ≥90% target. All 20 image-route
attempts failed for the OCR reason in §22, and the harness's
completeness check requires all four routes (typed, pasted, OCR, URL) to
succeed before consistency is even evaluated — so this 0% is a direct,
mechanical consequence of the OCR gap, not new evidence that the four
input modes produce different verdicts. The URL-route half of this
measurement was separately confirmed working (20/20 URL-route fixture
cases passed after the assertion fix in §32) and its claim/verdict
consistency with the corresponding typed cases was not the failure point.

## 24. Live-web observations (Phase 8, not accuracy — no gold labels)

90/90 completed (100%), 30/30/30 by difficulty. Verdict distribution:
SUPPORTED 59, UNSUPPORTED 11, MIXED_EVIDENCE 1, INSUFFICIENT_EVIDENCE 19.
Median latency 23.5s, p95 38.6s. These are observational only — no
independent gold label exists for live claims, so this is not reported as
accuracy, per Phase 8's explicit instruction.

## 25. Latency summary

| Stage | n | Median | p95 |
|---|---:|---:|---:|
| Typed (browser) | 60 | 2.56s | 3.35s |
| Pasted (modal) | 30 | 2.33s | 2.89s |
| URL (fixture, modal) | 20 | 2.67s | 3.18s |
| Public URL (real network) | 17 | 51.7s | 118.4s |
| Live web | 90 | 23.5s | 38.6s |

## 26. Memory / resource use

Peak RSS is captured per-trace via `resource.getrusage(RUSAGE_SELF)` in
`evaluation/hyper/final/application.py`'s `/evaluation/trace` endpoint for
every controlled/modal case; see `product-controlled.jsonl` /
`product-modal.jsonl` for the per-case series. No regression in peak memory
was observed relative to Group 2's model bake-off numbers
(`evaluation/hyper/GROUP2-RESULTS.md` §3) since the same model and process
architecture are in use; no separate memory benchmark was re-run in Group 4
beyond this per-case capture, as memory was not a Group 1–3 tuning target.

## 27. Model load time

Not separately re-measured in Group 4 (model revisions are unchanged from
Groups 1–3; see `evaluation/hyper/GROUP2-RESULTS.md` §3 for the original
load-time comparison across candidate NLI models).

## 28. Complete failure taxonomy — controlled investigations (48 errors)

| Category | Count | % |
|---|---:|---:|
| Eligibility filters (evidence retained but excluded pre-NLI, e.g. relevance/temporal/exclusion-reason filtering) | 21 | 43.8% |
| NLI prediction or confidence (raw neutral miss / under-threshold) | 11 | 22.9% |
| Aggregation / source weight / atomic coverage (false abstention despite some evidence) | 8 | 16.7% |
| Retained-evidence relation or source conflict | 7 | 14.6% |
| Retrieval/ranking produced no retained evidence at all | 1 | 2.1% |

**Hard-only breakdown (38 of the 48 errors are hard-difficulty cases):**
eligibility filters 52.6% (20), source conflict 18.4% (7), aggregation
15.8% (6), NLI prediction/confidence 10.5% (4), no-retrieval 2.6% (1).
Full per-case detail: `evaluation/hyper/final/results/investigation-errors.json`.

## 29. Complete failure taxonomy — NLI pairs

Of the false-negative contradiction misses (expected `contradict`, not
predicted `contradict`) on the held-out test split, categorized by the
actual stored raw/gated values (methodology matches Group 2's §2 pair-level
taxonomy):

| Cause | Count | % of misses |
|---|---:|---:|
| NLI prediction (raw top label was not contradict — neutral or opposite-direction support) | 38 | 62.3% |
| NLI confidence (raw label was contradict but below the 0.70 gate) | 9 | 14.8% |
| Relevance filter (evidence excluded pre-NLI) | 11 | 18.0% |
| Temporal/context filter | 4 | 6.6% |

61 total misses. The "NLI prediction" bucket (raw-model error, not a
threshold or filtering artifact) remains the dominant cause, consistent
with Group 2's original diagnosis that a meaningful share of contradiction
misses are the model being wrong at the representation level, not merely
under-confident. Full per-pair detail:
`evaluation/hyper/final/results/missed-contradictions.csv`.

## 30. Examples still wrong (representative, not exhaustive)

- Every SciFact-origin miss (20/44 = 45.5% of that subset) reflects the
  system's continued difficulty with dense, domain-specific scientific
  phrasing where the claim and the abstract share little surface overlap —
  the same failure mode Group 2 diagnosed as "raw-neutral" NLI misses,
  still present on genuinely new scientific claims.
- Several hard-difficulty "authority-vs-volume conflict" and "outdated-vs-
  current evidence" cases were answered `INSUFFICIENT_EVIDENCE` instead of
  the intended `MIXED_EVIDENCE` or a specific verdict — consistent with the
  "aggregation / source weight" 16.7% bucket in §28.
- The public-URL failures in §20 on real government/news pages (not
  synthetic fixtures) show the extraction pipeline still fails silently
  (no article text recovered) on a meaningful fraction of real-world pages,
  independent of any reasoning-quality question.

## 31. Software test totals (Phase 14, this pass — exact)

| Suite | Result |
|---|---|
| Backend (`pytest api/tests`) | **167 passed**, 3 warnings |
| `ruff check api evaluation` | All checks passed (25 pre-existing issues in new Group 4 scripts found and fixed — see §32) |
| `ruff format --check api evaluation` | 135 files, all formatted |
| Frontend lint (`eslint .`) | Clean, 0 errors |
| Frontend format (`prettier --check .`) | All matched files use Prettier code style |
| TypeScript (`next typegen && tsc --noEmit`) | Clean, 0 errors |
| Frontend unit tests (`vitest run`) | **13 passed** (5 files) |
| Extension tests (`node --test`) | **2 passed** |
| Production build (`next build` + standalone prep) | Succeeded, standalone server output verified |
| Playwright, Chromium + WebKit (`playwright.release.config.ts`) | **14 passed** (7 flows × 2 browsers), 0 failed |
| Accessibility (axe-core, embedded in 2 of the 14 Playwright flows) | 0 violations on both checked pages, both browsers |

No regression versus the pre-Group-4 baseline in any suite; the only
production-code change in this entire Group 4 pass is the one documented,
reasoning-neutral `evaluation/pass2/experiment.py` fix (§32), which the
backend suite's unchanged 167-pass count confirms did not alter production
behavior.

## 32. Harness fixes applied during this pass (Phase 11 protocol, full detail in `evaluation/hyper/final/HARNESS-FIXES.md`)

Three repair cycles, each documented / proven reasoning-neutral / re-locked
/ with all prior locks preserved:

1. **`evaluation/pass2/experiment.py` unpack crash** (blocking — nothing
   executed without it): `gate_stance` grew from 2 to 5 return values
   during Group 1–2; the shared harness's production-policy branch still
   destructured exactly 2. Fixed with `stance, exclusion, *_ = original_gate(...)`.
   Proven neutral by direct call comparison.
2. **Modal-stage OCR (30/30 failures) and cross-modal-URL (20/20 failures)
   harness bugs** — the same pair of bugs first seen in Groups 1–2, carried
   forward unfixed into this new harness copy. Per the user's explicit
   choice, the full run (controlled/URLs/live) was allowed to finish
   undisturbed first, then the 30-case modal stage alone was fixed and
   re-run fresh under a new lock. **Outcome was honestly mixed**: the
   cross-modal-URL fix (relaxing an exact-equality assertion to
   `.startsWith()` for the URL route only, since a synthetic-fixture
   extraction artifact — not a real decomposition defect — prevented exact
   equality) worked completely, 20/20 now pass. The OCR fix (synchronous
   response-body capture) did **not** resolve the underlying issue; all
   30/30 still fail identically, and this was reported as an unresolved
   limitation rather than pursued with further speculative fixes.
3. **Lint/format cleanup of the Group 4 harness scripts** (Phase 14,
   non-blocking — all inference had already completed): 25 lint findings
   and 5 unformatted files in scripts never run through the formatter
   before. Fixed by `ruff format`, `ruff check --fix`, and manually
   wrapping 4 remaining long string literals. Proven neutral by rebuilding
   `investigations.json` and `nli.json` from the edited scripts in an
   isolated scratch copy (byte-identical output, same SHA-256) and
   re-running `summarize.py` against the existing result files (byte-
   identical `summary.json`, same decision, same per-target booleans).

Nine locks in total are preserved, in order, under
`evaluation/hyper/final/results/lock-*.json`, ending in the active
`evaluation/hyper/final/lock.json`. No product case, prediction, or label
was altered, retried selectively, or removed at any point in this chain.

## 33. Readiness decision

## **NOT READY**

Computed automatically from the pre-committed Phase 10 targets against the
independent Hyper holdout, before any post-hoc adjustment:

| Target | Threshold | Measured | Met? |
|---|---:|---:|---|
| Overall accuracy | ≥80% | 80.8% | ✓ |
| Coverage | ≥70% | 65.2% | ✗ |
| Selective accuracy | ≥92% | 95.7% | ✓ |
| Easy accuracy | ≥95% | 91.7% | ✗ |
| Medium accuracy | ≥90% | 94.4% | ✓ |
| Hard accuracy | ≥60% | 62.0% | ✓ |
| Contradiction precision | ≥88% | 76.1% | ✗ |
| Contradiction recall | ≥65% | 58.1% | ✗ |
| False contradiction rate | ≤4% | 9.4% | ✗ |
| Public URL completion | ≥85% | 56.7% | ✗ |
| Pasted completion | ≥95% | 100% | ✓ |
| OCR completion | ≥90% | 0% (unmeasurable, §22) | ✗ |
| Cross-modal consistency | ≥90% | 0% (mechanically gated by OCR gap) | ✗ |

**5 of 13 targets met.** This is a strong development-to-holdout transfer
on pure verdict reasoning (accuracy, selective accuracy, medium and hard
difficulty all clear their bars, some for the first time on unseen data),
but a clear miss on coverage, contradiction recall/false-rate, and on every
product-input-modality metric that could be measured. A strong development
score paired with a materially weaker holdout score on several axes is, per
this project's own stated rule, evidence of more work needed — not evidence
of readiness.

## 34. Honest limitations

- **NLI recall/false-contradiction rate do not generalize.** Group 3's
  threshold tuning cleared its own validation-split targets comfortably; on
  genuinely new pairs, contradiction recall drops from 75.0%→58.1% and
  false-contradiction rate rises from 5.0%→9.4%. The threshold was tuned to
  a specific 188-pair validation split, not to the underlying phenomenon.
- **Coverage remains the single largest unresolved gap** (65.2% vs ≥70%
  target), driven by 41 false abstentions on cases with real, decidable
  evidence — mostly cases where retained evidence exists but is filtered
  out pre-NLI by eligibility/relevance rules (§28, 43.8% of all errors).
- **OCR could not be measured through browser automation for a third
  consecutive evaluation pass.** This is a harness limitation, not
  evidence the OCR feature itself is broken — the backend's direct OCR
  unit tests continue to pass — but it means no independent, product-level
  OCR accuracy number exists for this system.
- **Cross-modal consistency is unmeasurable as a real signal this pass**
  because it is gated on the broken OCR route; the 0% figure should not be
  read as "the four input modes disagree," only as "one of the four modes
  could not be exercised."
- **Public URL reliability (56.7%) reflects real extraction/timeout
  failures against real government, news, and JS-heavy sites** — a
  genuine, previously under-measured weakness distinct from reasoning
  accuracy.
- **Semantic (not exact) leakage between the old and new benchmarks cannot
  be fully ruled out** on a finite set of general-knowledge topics (§8).
- **SciFact-origin claims are markedly harder than authored claims**
  (54.5% vs 86.4% accuracy) — a domain-specific weakness on dense
  scientific phrasing.

## 35. Defensible CV / resume wording

- "Built and evaluated an automated fact-verification pipeline (NLI-based
  stance detection, multi-source evidence aggregation, claim-risk-gated
  abstention) achieving 80.8% verdict accuracy and 95.7% selective accuracy
  on a 250-case, independently constructed, leakage-audited held-out
  benchmark (not the development set used for tuning)."
- "Designed a frozen-system, pre-registered evaluation methodology (hash-
  locked configuration, pre-committed accuracy targets, single held-out
  run) to distinguish genuine generalization from development-set
  overfitting; identified and disclosed a threshold-tuning overfit in
  contradiction detection recall/false-positive rate via this process."
- "Diagnosed and taxonomized model failure modes across NLI stance
  prediction, evidence aggregation, and product input pipelines (OCR,
  URL extraction) using a 48-case controlled error analysis."

## 36. Claims NOT to make on a CV

- Do **not** claim "76% accuracy" (Group 3) or imply it was independently
  validated — it is a development-replay number on repeatedly-tuned data.
- Do **not** claim the system meets an ~80%+ accuracy bar "in production" —
  the 80.8% figure applies only to the controlled/fixture-evidence
  investigation set, with coverage at 65.2%, not to unconstrained live use.
- Do **not** claim OCR or cross-modal consistency were "verified" or
  "tested" at the product level — both are documented as unmeasurable
  through this evaluation's harness in this pass.
- Do **not** claim URL-based fact-checking is production-reliable — 56.7%
  completion on a real, diverse URL sample is a real, currently-unresolved
  weakness.
- Do **not** claim the contradiction-detection threshold is well-calibrated
  — recall and false-contradiction rate both missed their independent-
  holdout targets after appearing calibrated on development data.

---

### Source data

All raw results, locks, audits, and generation scripts referenced above
live under `evaluation/hyper/final/`. Development-generation reports:
`evaluation/hyper/GROUP1-RESULTS.md`, `GROUP2-RESULTS.md`,
`GROUP3-RESULTS.md`. Original locked baseline: `evaluation/final/` and
`docs/final-reliability-report.md`.
