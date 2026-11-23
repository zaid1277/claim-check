# Claim Check — Targeted Remediation Report (Pass 5)

This pass targeted four specific weaknesses the independent Group 4 Hyper
holdout exposed: contradiction generalization, coverage/false abstention,
public-URL ingestion, and OCR/cross-modal measurement. It did not rewrite
the architecture. All tuning decisions were made from NEW development data
(a fresh 684-pair multi-fold contradiction corpus); the Group 4 Hyper
holdout was used only diagnostically, never to choose a threshold. A
second, independent NEW confirmation holdout (150 investigations / 280 NLI
pairs / 20 URLs / 20 OCR / 10 cross-modal) was built, frozen against, and
run exactly once, per the stop condition.

## 1. Hyper holdout failure analysis (recap, diagnostic only)

Group 4's independent holdout showed: contradiction precision 76.1% /
recall 58.1% / false-contradiction rate 9.4% (all missed their targets,
despite clearing them on Group 3's own development validation split);
coverage 65.2% with 41 false abstentions; OCR and cross-modal unmeasurable
due to a Playwright/CDP harness bug; public URL completion 56.7%. These
four gaps set this pass's exact scope. See `docs/hyper-final-reliability-report.md`
for the full original analysis.

## 2. Contradiction generalization diagnosis

Group 3's threshold (confidence ≥0.70, no relevance corroboration) was
tuned only against its own 120-pair validation split. It was never
cross-validated, so its apparent 88.2%/75.0%/5.0% precision/recall/false-
rate was a single-split measurement, not a generalization guarantee — the
Group 4 holdout exposed exactly that gap.

## 3. Multi-fold contradiction results

New corpus: `evaluation/remediation/data/contradiction-corpus.json`, 684
pairs (228/label), 3 balanced folds, mined fresh from the ANLI pool (600
new pairs, disjoint from every prior corpus) plus 84 hand-authored pairs
across 14 stress categories (same-entity/different-predicate, subtle
negation, date/number mismatch, causal-vs-correlational, partial
entailment, lexical-overlap traps, long-passage distraction, paraphrased
contradiction, entity-role reversal, ranking claims, temporally-compatible-
different-facts, similar named entities, implicit contradiction). Leakage
audit: 0 exact overlaps / 0 near-duplicates / 0 internal duplicates against
7,133 prior items. Full sweep results: `evaluation/remediation/results/fold-analysis.json`.

No single confidence threshold clears precision≥85%/recall≥65%/false-
contradiction≤5% simultaneously (same Pareto-limit pattern Group 3 found,
now confirmed independently). Adding a **second, relevance-corroboration
signal** for contradiction predictions specifically moved the frontier:
at threshold 0.68 + relevance floor −1.5, mean **precision 0.869 (min
0.852), recall 0.671 (min 0.658), false-contradiction rate 0.0504 (max
0.059)** — stable across all 3 folds, the closest configuration found to
all three targets (recall/precision clear comfortably; false-contradiction
rate misses the aspirational ≤5% by 0.4 points, reported honestly rather
than force-fit).

## 4. Model stability comparison

| Model | Macro F1 (mean±std, 3 folds) | Latency (median ms) | Params (M) |
|---|---:|---:|---:|
| Current (adopted): DeBERTa-v3-large-mnli-fever-anli-ling-wanli | **0.768 ± 0.012** | 267.5 | 435.1 |
| Previous base: DeBERTa-v3-base-mnli-fever-anli | 0.624 ± 0.030 | 84.8 | 184.4 |
| Alternative: cross-encoder/nli-deberta-v3-small | 0.341 ± 0.022 | 45.6 | 141.9 |

Current model wins decisively and most stably — no model change made.
`facebook/bart-large-mnli` (the originally intended third candidate)
reproducibly crashed this environment with SIGBUS on the first inference
batch (a previously-documented class of issue on this hardware, per an
existing code comment for the smaller relevance model); substituted the
smaller cross-encoder, clearly weaker anyway.

## 5. Proposition-alignment (two-signal) gating results

Implemented in `api/app/services/pipeline.py`: `gate_stance` now applies a
**contradiction-specific relevance floor** (−1.5, vs the general 0.0 floor
unchanged for support/neutral) before demoting contradiction evidence to
neutral, alongside `min_contradiction_confidence` lowered 0.70→0.68. The
continuous relevance-weight curve (evidence_score scaling) is unchanged;
only the retain-vs-exclude decision differs for contradiction. Diagnostic
replay against the Hyper holdout's 41 false abstentions found only 2/41
would be recovered by this change — a modest, honestly-reported effect,
not overstated.

## 6. False-abstention taxonomy

Fine-grained classification of the Hyper holdout's 41 false abstentions
(diagnostic-only use, per the "no re-tuning on it" rule):

| Cause | Count | % |
|---|---:|---:|
| Relevance score too low | 20 | 48.8% |
| NLI raw-neutral (genuine model miss, not a filter) | 12 | 29.3% |
| Claim-risk high-risk evidence minimum | 4 | 9.8% |
| Claim-risk independent-source restriction | 2 | 4.9% |
| Evidence minimum not met (standard risk) | 2 | 4.9% |
| Missing retrieval | 1 | 2.4% |

Most "relevance too low" cases are SciFact-origin (dense scientific
abstracts scoring systematically negative on the general-purpose
relevance cross-encoder — a domain-calibration issue) and were
already-correctly-neutral NLI outputs, not real signal being discarded.
Claim-risk restrictions (independent-source count, high-risk evidence
minimum) were deliberately **not** loosened — they are a Group-1 safety
feature protecting against confidently-wrong medical/financial claims
backed by a single source.

## 7. Coverage calibration curve

**Not separately re-derived this pass.** `minimum_evidence` was already
extensively calibrated by Group 3 against its own coverage/selective-
accuracy curve and was not the dominant false-abstention cause found in
§6 (only 2/41, standard-risk). Given the time budget and that the
taxonomy pointed at the relevance floor (addressed in §5) rather than the
evidence-total threshold, this is a disclosed scope limitation, not a
claim that coverage is solved.

## 8. URL failure taxonomy

Direct-extraction testing (bypassing the browser harness, to isolate
genuine extraction failures from browser/network flakiness) against the
original 30 previously-failing Group-4 URLs and a new 50-URL dev set
found concrete causes: **404/stale URL** (benchmark-construction issue,
not a product bug), **bot-protection/WAF blocks (403)** — confirmed
genuine by testing a standard browser User-Agent, which did not help;
these are real, and per Part 11 were **not** bypassed, **download-limit
exceeded** (the original 2MB cap rejected legitimate long articles, e.g.
full Wikipedia pages), **trafilatura over-strict extraction** on
legitimate but nav-heavy pages, and **transient network errors** (a
meaningful share of raw "network-error" failures succeeded on an
immediate identical retry — ordinary internet flakiness). One genuine TLS
certificate-verification failure was traced to this sandbox's own network
path (a self-signed cert in the chain) and is disclosed as a testing-
environment artifact, not fixed by weakening certificate verification in
production.

## 9. URL fallback architecture

`api/app/services/url_fetch.py` and `api/app/services/article_extraction.py`,
general-purpose only, no site-specific rules:
1. Standard HTTP fetch (unchanged), now with **one retry on transient
   network errors only** (never on deterministic outcomes like 403/404).
2. `trafilatura.extract`, strict (unchanged, tried first).
3. `trafilatura.extract` with `favor_recall=True` (documented library
   fallback mode) if strict finds nothing.
4. JSON-LD `articleBody`/`description` or Open Graph description, if
   trafilatura (both modes) finds nothing.
5. A generic, fully site-agnostic visible-text tag-stripping fallback, as
   a last resort.
6. Download limit raised 2MB→6MB (still bounded).
7. `ProviderError` now carries an optional `category` tag (invalid-url,
   dns-error, bot-protection-or-access-denied, not-found,
   unsupported-content-type, download-limit-exceeded, redirect-loop,
   tls-error, network-error, no-readable-text) for diagnostics only — the
   user-facing message is unchanged in every case.

**Deliberately not implemented:** a headless-browser-render fallback for
JS-heavy pages. Diagnostic testing found none of the actual observed
failures were JS-rendering issues (every failing page returned real
server-rendered HTML); adding a browser-automation dependency to the API
service would be a genuine architecture change, out of scope for a
targeted pass, for no measured benefit against the failures actually
found.

All 14 new/changed backend unit tests (`api/tests/test_articles.py`) pass
unchanged.

## 10. OCR harness fix

Root-caused this time, not just patched: two earlier fix attempts (a
deferred `page.waitForResponse().json()`, then a synchronous
`page.on("response", ...)` handler) both still hit "Protocol error
(Network.getResponseBody): Request content was evicted from inspector
cache" because **both read the response body through Chromium's CDP
Network-domain inspector cache**, which this isolated Next.js dev-server
setup evicts regardless of timing. The actual fix: intercept the request
with `page.route()` + `route.fetch()`, which performs the real HTTP
request through **Playwright's own network layer**, never touching
Chromium's CDP inspector cache at all — `route.fulfill({response})` then
passes the real response to the page unchanged. Verified in isolation
first (5/5 clean cases via a standalone reproduction script) before
adopting it in the confirmation harness. See
`evaluation/remediation/final/HARNESS-FIXES.md`.

## 11. OCR metrics (confirmation holdout, 20 fixtures)

**19/20 image-route cases completed (95%)** — up from 0/30 in Group 4 (an
unmeasurable harness gap for three consecutive prior evaluation passes).
The one failure timed out waiting for the post-OCR UI state (not the CDP
eviction bug — the `route.fetch()` capture itself succeeded); reported
honestly as an unresolved, isolated case rather than retried, per the
run-once rule. Latency: median 3.50s, p95 3.92s. CER/WER per-fixture
detail: `evaluation/remediation/final/results/ocr-observations.jsonl`.

## 12. Cross-modal results

**Raw (exact-signature) consistency: 0/10.** All 10 four-way comparisons
are confounded by a previously-documented, unfixed fixture artifact: the
controlled URL-route fixture's `document()` helper appends boilerplate
text after the claim with no separating space, so the URL route's
proposed claim text never exactly matches the typed/pasted/OCR routes'
(same root cause as Group 4's §23). **Verdict-only comparison (ignoring
the known boilerplate text difference): 7/10 consistent.** The 3
genuine disagreements (`remediation-fact-004/014/049`) all flip
SUPPORTED→INSUFFICIENT_EVIDENCE for the URL route specifically — a real,
disclosed finding that appended boilerplate can dilute evidence-matching
enough to change a verdict, not merely a test-harness cosmetic issue.
Neither the harness nor the production code was altered after this
result was observed (post-hoc analysis of already-recorded data, not a
re-run).

## 13. Confirmation holdout construction

`evaluation/remediation/final/`: 150 investigations (40 easy / 50 medium /
60 hard: 115 authored + 35 fresh SciFact), 280 NLI pairs (160 mined ANLI +
120 generated from 40 fresh fact triples), 20 public URLs, 20 OCR
fixtures, 10 cross-modal cases. Disjoint from Pass 2, the old final
corpus, the Group 4 Hyper holdout, AND this pass's own dev-only
multi-fold contradiction corpus (never reused for the confirmation set).

## 14. Independence/leakage audit (confirmation holdout)

Two automated audits (`build_and_audit_nli.py`, `audit_investigations.py`):
initial passes found 4 exact NLI-fact collisions and 19 investigation
collisions (mostly a repeated noise-boilerplate string and several common
trivia facts coincidentally reused from prior corpora) — all replaced with
different content; final audits are clean: **0 exact overlaps, 0
near-duplicates, 0 internal duplicates**, scanning 8,191 (NLI) / 8,718
(investigations) prior items respectively, including the Group 4 Hyper
holdout and this pass's own dev corpus.

## 15. Confirmation NLI metrics (280 pairs, independently held out)

| Metric | Confirmation | Hyper holdout (Group 4) |
|---|---:|---:|
| Macro F1 (gated/production) | 73.7% | 65.5% |
| Contradiction precision | **85.7%** ✓ | 76.1% |
| Contradiction recall | **66.7%** ✓ | 58.1% |
| False contradiction rate | **4.52%** ✓ | 9.4% |

**All three of this pass's primary contradiction targets are met on the
independent confirmation holdout**, and the measured values (P=85.7%,
R=66.7%, FCR=4.52%) land very close to the dev multi-fold estimate
(P=86.9%, R=67.1%, FCR=5.04%) — real evidence of genuine generalization,
not overfitting to the dev corpus. By origin: authored pairs 98.3%
accuracy, ANLI-mined pairs 55.0% (ANLI is adversarially constructed to be
hard by design).

## 16. Confirmation verdict metrics (150 investigations)

Overall accuracy **76.0%**, coverage **62.0%**, selective accuracy
**91.4%**, confident errors 8, correct abstentions 29, false abstentions
28.

## 17. Easy/medium/hard accuracy

| Difficulty | n | Accuracy | Target | Met? |
|---|---:|---:|---:|---|
| Easy | 40 | 90.0% | ≥95% | ✗ |
| Medium | 50 | **98.0%** | ≥90% | ✓ |
| Hard | 60 | 48.3% | ≥60% | ✗ |

Hard accuracy is notably lower than Group 4's Hyper holdout (62.0%).
Partial confound: this confirmation set's hard tier is 58% SciFact-origin
(35/60) vs Group 4's 44% (44/100) — SciFact claims are markedly harder
(51.4% vs 83.5% accuracy by origin here), so a higher SciFact share alone
drags the aggregate down; the two hard-accuracy numbers are not a clean
apples-to-apples comparison. This does not fully explain the drop and is
disclosed as an open weakness, not explained away.

## 18. Contradiction P/R/F1

See §15 — precision 85.7% / recall 66.7% / F1 75.0%, all targets met.

## 19. False contradiction rate

4.52%, target ≤5% — met, a substantial improvement from Group 4's 9.4%.

## 20. Coverage

62.0%, target ≥70% — missed, and lower than Group 4's 65.2%. Not
separately re-tuned this pass (§7); remains the largest unaddressed
generalization gap alongside hard/easy accuracy.

## 21. Selective accuracy

91.4%, target ≥93% — missed by 1.6 points, though still in the
historically-strong 91–98% range this system has shown across every prior
generation. The one metric this project has never failed to keep high.

## 22. URL results

**13/20 completed (65%)**, target ≥80% — missed, and notably lower than
the isolated dev-benchmark measurement (41/50 = 82%, §8-9) taken via
direct extraction calls outside the browser/Next-dev-server/investigation
pipeline. All 7 confirmation-holdout failures were `page.waitForResponse`
timeouts (150s), not extraction-category errors — pointing at
browser+pipeline-level latency/resource contention under this harness,
distinct from the raw extraction-layer improvements verified in §8-9.
Reported honestly as a real, unresolved product-workflow gap, not
conflated with extraction-layer accuracy.

## 23. OCR results

See §11 — 19/20 (95%), target ≥90%, met.

## 24. Latency

| Stage | n | Median | p95 |
|---|---:|---:|---:|
| Typed (browser) | 30 | 2.44s | 3.70s |
| Pasted (modal) | 20 | 2.16s | 2.75s |
| OCR (modal) | 19 | 3.50s | 3.92s |
| URL (fixture, modal) | 10 | 2.30s | 2.63s |
| Public URL (real network) | 13 | 48.6s | 94.3s |

## 25. Test totals (Phase-14-equivalent software verification)

| Suite | Result |
|---|---|
| Backend (`pytest api/tests`) | **167 passed**, 3 warnings |
| `ruff check api evaluation` | All checks passed |
| `ruff format --check api evaluation` | 149 files, all formatted |
| Frontend lint (`eslint .`) | Clean, 0 errors |
| Frontend format (`prettier --check .`) | All matched files use Prettier code style |
| Frontend unit tests (`vitest run`) | **13 passed** (5 files) |
| Extension tests (`node --test`) | **2 passed** |
| Playwright, Chromium + WebKit (`playwright.release.config.ts`) | **14 passed** (7 flows × 2 browsers), 0 failed |
| Accessibility (axe-core, embedded in 2 of the 14 flows) | 0 violations, both browsers |

No regression in any suite versus the pre-remediation baseline. Production
code touched this pass: `api/app/services/pipeline.py` (contradiction
gating), `api/app/core/settings.py` (two new/changed settings),
`api/app/services/url_fetch.py` and `article_extraction.py` (layered
extraction), `api/app/core/errors.py` (additive `category` field). No
frontend/extension code touched.

## 26. Remaining limitations

- **Coverage (62.0%) and hard-difficulty accuracy (48.3%) remain below
  target** and were not the focus of this pass's changes; §7/§17 disclose
  why and what wasn't attempted.
- **Overall verdict accuracy (76.0%) is lower than Group 4's Hyper
  holdout (80.8%)** — the contradiction and OCR fixes did not translate
  into a net accuracy gain on this specific confirmation set, likely
  compounded by its harder SciFact-heavy hard tier (§17) and by selective
  accuracy/coverage both softening slightly.
- **Public URL completion (65%) is well below target and below even this
  pass's own isolated extraction-layer measurement (82%)** — a real
  browser/pipeline-level gap distinct from the genuine extraction
  improvements made.
- **Cross-modal consistency remains confounded by an unfixed fixture
  artifact** (§12); the verdict-only reading (70%) is informative but
  still below target, and includes 3 genuine verdict-flip cases worth
  further investigation.
- **False-contradiction rate (4.52%) clears its target but only barely**
  under the dev-derived operating point (0.0504 on dev, itself already
  just above the aspirational 5% ceiling) — this remains a tight margin,
  not a comfortably solved problem.
- **SciFact-origin claims remain much harder than authored claims**
  (51.4% vs 83.5%) — unchanged from Group 4, not addressed this pass.

## Readiness decision: **NOT READY**

6 of 13 pre-committed targets met (contradiction precision, recall, false-
contradiction rate, pasted completion, OCR completion, medium accuracy).
7 missed (overall accuracy, coverage, selective accuracy, cross-modal,
public URL, easy accuracy, hard accuracy). This pass's primary objective —
contradiction generalization — was genuinely and independently achieved,
and OCR measurement was genuinely fixed after three prior failed
evaluation passes. But core verdict accuracy, coverage, and hard-case
accuracy did not improve and URL/cross-modal remain clearly below target.
Per this project's own standing rule, a strong result on the pass's
targeted metrics alongside a weaker-or-flat result on core accuracy is
evidence of more work needed, not readiness.
