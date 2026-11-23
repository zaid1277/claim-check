# Demo guide

A short, low-risk sequence for showing Claim Check live, plus backups in
case a live search result looks different on the day. Every example below
is an **easy-tier claim that was actually measured** in the most recent
independent confirmation holdout ([`docs/remediation-final-report.md`](remediation-final-report.md)),
not a hand-picked untested claim.

**Live-web caveat, read this first:** every example marked "live mode"
depends on real-time web search. Search results, page availability, and
extraction can change day to day — a claim that measured correctly during
evaluation is *not* guaranteed to produce the same verdict on every future
run. That's inherent to live web research, not a bug, and it's worth saying
out loud during a demo rather than promising a guaranteed outcome. If a live
example doesn't behave as expected, switch to fixture mode or one of the
backups below rather than improvising a new, unverified claim live.

## 0. Zero-risk opener (fixture mode, no search needed)

Click **Use demonstration claim**, then **Check claim**. This uses the
built-in fixture claim ("The demonstration library opens on Sundays.")
against clearly labelled synthetic evidence — no live search, no network
variability, always available even offline. Good for explaining the UI
(evidence categories, the "Why this evidence?" disclosure, the methodology
link) before touching live data.

## 1. Supported claim (live mode)

> **"The first modern Olympic Games were held in Athens in 1896."**

A clean, well-documented historical fact. Good for showing a straightforward
**Supported** verdict with strong, easy-to-recognize sources (encyclopedic
and reporting sources typically dominate the evidence list).

**Backup:** "The Boston Tea Party took place in 1773."

## 2. Unsupported claim (live mode)

> **"Plastic pollution poses no threat whatsoever to marine ecosystems."**

An absolute claim that's easy for evidence to contradict clearly. Good for
showing the **Unsupported** verdict and the "Evidence against" section
specifically — walk through the "Why this evidence?" disclosure to show the
retained NLI stance and confidence for a contradiction.

**Backup:** "The euro is the official currency used by every country in
Europe." (a slightly-too-strong version of a true claim — a reliable way to
get a contradiction without relying on a genuinely false statement)

## 3. Article URL flow (live mode)

Pick a current, stable news article (e.g. from a major wire service) and
use the **Article URL** input mode. This demonstrates: live extraction,
the editable sentence-proposal review step, and picking specific sentences
to investigate. If the URL fails to extract (paywalls and bot protection do
happen), that's the moment to show the **fallback**: switch to **Pasted
article**, paste the visible text, and continue — the honest failure→recovery
path is itself worth demonstrating, not just the happy path.

## 4. Screenshot / OCR flow (fixture or live)

Take a screenshot of any short paragraph of text (a news snippet, a
Wikipedia paragraph) and use the **Screenshot / image** input mode. This
shows: local OCR extraction, the mandatory review-and-correct step (point
out that the *edited* text is what gets investigated, not the raw OCR
output), then claim proposal from the corrected text.

## 5. Browser extension (live mode)

With the extension loaded (see the root README's "Browser Extension"
section), highlight a sentence on any web page, right-click **Check with
Claim Check**, and submit from the side panel. Good closer — shows the
same backend and evidence pipeline working from a second client.

## What to say about verdict types during a demo

Claim Check has four outcomes — Supported, Unsupported, Mixed Evidence, and
Insufficient Evidence. The examples above are chosen to reliably show the
first two live; Mixed Evidence and Insufficient Evidence are real, correct
outcomes for genuinely ambiguous or under-evidenced claims, but harder to
guarantee on demand from live search. If asked to show one, the honest
answer is: point to the report screenshot in the README, or note that
abstention is intentional — a system that never says "not enough evidence"
would be manufacturing false confidence, not a better product.

## Don't do this in a demo

- Don't claim a specific accuracy percentage as "how often it's right" —
  point to [`docs/remediation-final-report.md`](remediation-final-report.md)
  for the actual measured numbers and their caveats instead.
- Don't promise a live claim will produce the same verdict every time.
- Don't skip the "Why this evidence?" disclosure — it's the most convincing
  part of the product, because it shows the reasoning isn't hidden.
