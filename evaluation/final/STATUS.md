# Final release evaluation — complete, NOT READY

The full locked release ran to completion on 14 September 2026: 348-pair NLI
holdout, both 175-case controlled runs (Pass 2 frozen and candidate), the
50-case modal batch, all 25 public URLs, and all 60 live-web claims, followed
by the software verification suite. See `docs/final-reliability-report.md` for
full results. Readiness decision: **NOT READY** (2 of 14 pre-committed targets
met). Do not tune reasoning against these results without a new benchmark
version, per the original protocol.

## Harness fix and re-lock (14 September 2026)

The first attempt to run the locked release (`evaluation/final/run_release.sh`)
found that the held-out NLI holdout completed normally, but every product-facing
mode (baseline/controlled/modal/urls/live) failed immediately. Root cause:
`evaluation/final/application.py`'s `/evaluation/trace` endpoint never returned
`variant`/`stage`, while `evaluation/final/product.mjs` asserts on both right
after startup. This is a defect in the evaluation harness itself (test
infrastructure), not in the product's reasoning, models, thresholds, prompts, or
data, and it had never been exercised end-to-end before — the one prior passing
"smoke" run used the separate, older `evaluation/pass2/` harness, not this file.

With explicit user authorization, `application.py`'s `get_trace()` was changed to
also return the already-computed `variant` and `stage` module-level values (no
other line changed). Because that file is part of the hashed lock set, the lock
was regenerated with `evaluation/final/freeze.py`:

- Old lock preserved at `evaluation/final/results/lock-before-harness-fix.json`
  (sha256 `9827d2e35105971d0a6cc9c12fdafa93ebf76fe94b78097bf7a115e325ba147a`).
- New lock sha256: `d98bd0890a4f346c9b98569670af3d9ce049018b42071f396c2c010919022763`.
- Diff between old and new lock confirmed exactly one `files` hash entry changed
  (`evaluation/final/application.py`); `archive_sha256` and `created_at` changed
  as a mechanical consequence of re-packaging the source snapshot. No model
  revision, package version, configuration value, threshold, or any other frozen
  file hash changed. `baseline/pass2-source.tar.gz` (sha256
  `62653886370423bf1c44f6493876d0ffa4612246d584f03f423a995e31e54bf4`) was not
  touched.
- Stale artifacts from the crashed attempt (`final-pairs.json`, `final-pairs.log`,
  `api-pass2.log`, `product-baseline.log`) were removed so the full release,
  including the NLI holdout, reruns cleanly from scratch under the new lock.

No reasoning, model, threshold, prompt, source-weighting, contradiction rule, or
benchmark label was changed. No product case was relabeled, retried selectively,
or excluded.

## Second harness fix and re-lock (14 September 2026, same day)

After the first fix, the release ran successfully through the NLI holdout, the
full 175-case Pass 2 baseline, the full 175-case candidate controlled run, and
the 50-case modal run, then partway (20/25) through the public-URL run before
`product.mjs` crashed with an uncaught promise rejection: a `page.waitForResponse`
call created its wait-promise before the triggering click, and under a slow
network response the promise could settle before the code reached its `await`,
crashing the whole Node process instead of being caught by `attempt()`'s
try/catch (which correctly recorded 7 other URL cases as failures). All 4 call
sites with this same "create the wait-promise, click, then await it" pattern
(`submitButton`, the OCR image wait, the modal proposal wait, the URL proposal
wait) were given an immediate no-op `.catch(() => {})` on the wait-promise. This
only prevents the unhandled-rejection crash; the real result/error still flows
through the original `await` and into `attempt()`'s existing error handling
exactly as before — no case outcome logic changed.

- Old lock preserved at
  `evaluation/final/results/lock-before-second-harness-fix.json`.
- New lock sha256: `dcb01c99687b6f3582aa5be7fa40cce85b3f0b5ccbe908b6136d3a7a10e37771`.
- Diff confirmed exactly one `files` hash entry changed
  (`evaluation/final/product.mjs`); nothing else, including
  `baseline/pass2-source.tar.gz`, changed.

The run was resumed, not redone: `product.mjs`'s journal already skips any case
key already recorded, so the completed NLI holdout, Pass 2 baseline, candidate
controlled, and modal results stand unchanged; only the remaining public-URL
cases and the live-web batch ran fresh under the new lock.

## Resume state

The disposable PostgreSQL instance and isolated web server were already running
when the harness fixes were applied; the full release was relaunched under
`caffeinate -i` after each re-lock. See `evaluation/final/results/` for the
current run's logs and `docs/final-reliability-report.md` for the final report
once complete.
