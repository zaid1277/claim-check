# Portfolio release verification — 23 November 2026

Release scope: a public, reproducible research/portfolio preview, not a production
verification service. No model, threshold, scoring formula, source weight or
historical benchmark was changed. A subsequent retrieval correction and research
review are recorded in [the accuracy pass](accuracy90-research.md).

## Fresh checks

| Check | Result |
| --- | --- |
| Full backend, cached real NLI and isolated PostgreSQL 17 | 175 passed, no skips, 3 dependency deprecation warnings |
| Frontend unit tests | 13 passed |
| Extension tests | 2 passed |
| Chromium and WebKit release flows | 14 passed; includes one/five selected article claims, slow API, reports, OCR correction, responsive/accessibility and setup flows |
| Ruff lint / formatting | Passed; 169 Python files formatted |
| ESLint / Prettier / TypeScript | Passed |
| Production frontend build | Passed |
| Installed Python dependency consistency | `pip check` passed |
| Publishable file scan | No matching provider/GitHub token or private-key patterns; environment files, local state, caches and model weights ignored |

The ordinary backend run skips opt-in database/model tests. The 175-test result
above explicitly enabled both with `RUN_LOCAL_NLI_TESTS=1` and
`TEST_DATABASE_URL` pointing at a disposable database. Tests use installed
local dependencies, not a clean hosted CI environment.

Four new input-consistency regressions exercise typed, pasted, URL and corrected
OCR input through the API, investigation, saved report and share report. HTML
and OCR outputs are controlled in these regressions; they verify that the same
reviewed claim has the same assessment, not real OCR accuracy or live retrieval.
The browser suite also uses controlled evidence and mocked OCR.

## Fresh live smoke test

Claim: “The Eiffel Tower is in Paris.” Real Tavily search, cached configured
DeBERTa-v3-large NLI, and disposable PostgreSQL were used.

- API returned HTTP 200 and **SUPPORTED**.
- The retrieved Wikipedia passage describing a lattice tower on the Champ de
  Mars in Paris was **support**, with NLI confidence **0.9996637105941772**.
- The saved report returned HTTP 200; all assessments matched on reload.
  `created_at` used equivalent UTC/local offsets, so literal JSON timestamp
  strings differed while representing the same instant.

This is one smoke test, not a new accuracy benchmark. The frontend category is
covered by existing component/browser tests; this live request itself ran via
the API, not a manual live-browser investigation.

## Release changes

- `scripts/verify.sh --browser` and GitHub Actions now use the isolated release
  configuration for Chromium **and** WebKit, including the slow article flow.
- Added `api/tests/test_input_consistency.py` (four parameterized cases).
- README links to the intended GitHub repository and removes an overgeneralized
  claim that controlled results establish a universal local-model accuracy ceiling.

## Reliability limits remain

The completed independent confirmation evaluation remains the current research
result: 76.0% verdict accuracy, 62.0% coverage and 91.4% selective accuracy on
150 controlled investigations. See [the remediation report](remediation-final-report.md).
Public URL completion and hard-case accuracy missed targets. Earlier OCR harness
problems were addressed in that pass, but its cross-modal results remain limited
by the documented URL fixture problem. Those historical results were not rerun,
rewritten, or used to tune production behavior here.

A clean GitHub Actions run, public deployment/container testing and manual
installed-extension validation are separate gates. Publishing source code does
not establish that those gates passed. This release should be marked a
**pre-release/portfolio preview**, not production-ready.

## Reproduce

```sh
./scripts/verify.sh --browser
# Optional full integration verification (install ML extras and cache models first):
RUN_LOCAL_NLI_TESTS=1 HF_HUB_OFFLINE=1 \
  TEST_DATABASE_URL='postgresql://USER:PASSWORD@localhost:5432/TEST_DATABASE' \
  api/.venv/bin/python -m pytest api/tests -q
```

Use a disposable database for tests. Install browser binaries with
`cd web && npx playwright install chromium webkit` before the browser suite.
Never commit provider credentials or local database connection files.

## Clean-install findings

The first hosted run exposed stale dependency locks (missing spaCy/tldextract).
The next exposed a missing metrics-test dependency and two unit tests that
accidentally loaded optional models. Both were corrected: locks were regenerated,
scikit-learn declared as a development dependency, and those mechanics tests now
inject relevance scores. Real-model coverage remains in the opt-in integration
suite. Two lock-completeness tests prevent the first issue recurring.

Final local backend verification after these repairs and the retrieval correction:
**175 passed, no skips**. Hosted CI status must be read from GitHub Actions.
