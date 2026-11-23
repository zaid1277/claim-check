# Remediation pass 5 (confirmation holdout) — harness-only repairs

Same phase-11-style protocol used throughout Group 4: a harness bug may be
repaired only if it prevents evaluation from executing; each repair is
documented, proven not to alter reasoning, re-locked, with the previous
lock preserved, and resumed without removing recorded product data.

## Repair: `product.mjs` used an incompatible web-server port

**Blocking symptom:** the confirmation-holdout `product.mjs` was written
to expect the isolated evaluation web server on `http://127.0.0.1:3103`
(chosen to avoid colliding with a lingering Group 4 debug instance on
3102), but nothing ever listened on 3103 -- `curl` to it returned
connection-refused, so every "controlled" (browser route) and "modal"
case would have failed immediately.

**Root cause:** `evaluation/final/serve-web.mjs` (shared, unmodified
infrastructure reused verbatim from Group 3/4 -- not something this pass
touches) hardcodes `port: 3102` in its `next(...)` call and its
`.listen(3102, ...)` call; it is not configurable via an environment
variable or argument. Assuming it would follow the API's port offset
(8103 -> 3103) was simply wrong -- it always listens on 3102 regardless
of which API port it's told to proxy to via `API_BASE_URL`.

**Fix:** `product.mjs`'s `web` constant changed from
`http://127.0.0.1:3103` to `http://127.0.0.1:3102`, matching
`serve-web.mjs`'s real, fixed port. `api` stays `http://127.0.0.1:8103`
(already correct and already verified working via a direct health-check).
One line changed, a port number only.

**Proof this does not alter reasoning:** `serve-web.mjs` itself was not
touched (it isn't part of this pass's frozen file set to begin with,
same as in Group 4). The change only tells the *test driver* which port
to connect to for browser navigation -- it does not touch any
extraction/NLI/aggregation/scoring code path, and the API port (where all
actual investigation logic runs) is unchanged.

**Re-lock:**

1. `results/lock-before-port-fix.json` -- sha256
   `2cc52ecd4463f2bd740fd7a825d9305f18f8b4c46dd3afacc5482106267a3bfc`
   (the comprehensive `--final` freeze, 176 files, computed immediately
   after remediation was complete and all confirmation-holdout benchmark
   data was built -- before this fix).
2. `lock.json` (active) -- sha256
   `743f6ccb07f3b467e0a29130e8b328787c6b95dd0ad42e9efd69615be0f3201f`
   (diffed against lock #1: exactly one file changed --
   `evaluation/remediation/final/product.mjs` -- zero files added, zero
   removed, and critically zero changes anywhere in `api/app`, `web/`,
   `extension/`, or any benchmark data file: `data/investigations.json`,
   `data/nli.json`, `data/images.json`, `data/public-urls.txt` are all
   absent from the changed-file list).

`evaluation/remediation/final/results/final-pairs.json` (the 280-pair NLI
holdout inference) was generated before this fix and did not need to be
regenerated: it is pure Python model inference with no dependency on
either server's port, so its results stand unaffected. No product case,
prediction, or label was altered, retried selectively, or removed as part
of this fix.

**Note on the fixed point:** this documentation file is itself part of the
frozen file set, so writing it changes the lock's hash again after lock #2
above was computed. `results/lock-before-harness-doc.json` (identical to
lock #2) is the archived intermediate; `lock.json`'s live hash --
`e7a8d26d3c0561c0ca5796700145ad45645ceea9d68f76d17c489943d432cc73` -- is
the true terminal state, computed immediately after this file's last edit,
with no further changes to it afterward.
