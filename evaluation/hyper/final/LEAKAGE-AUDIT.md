# Group 4, Phase 4 — Independence / leakage audit

## Method

Two automated audits, both hash-based (SHA-256 of case-folded, whitespace-
normalized text) plus a word-Jaccard near-duplicate check, run against every
corpus and probe set found anywhere under `evaluation/` in this repository:
the original Pass 2 corpus (`evaluation/pass2/`), the old final corpus
(`evaluation/final/`), the reliability corpus (`evaluation/reliability/`),
every Group 1-3 probe set (`retrieval-probes.json`, `compound-probes.json`),
the historical missed-contradiction pairs, and every prior `nli.json`.

- `evaluation/hyper/final/build_and_audit_nli.py` — audits the new 804-pair
  NLI holdout.
- `evaluation/hyper/final/audit_investigations.py` — audits the new 250-case
  investigation set.

## NLI holdout audit results

- 5,047 prior texts scanned (before the investigation set existed; expands
  to the same scan the investigation audit ran against).
- **Internal near-duplicates: 0. Exact overlap with prior corpora: 0.
  Near-duplicate claims (≥90% word Jaccard): 0.**
- One methodological note, documented and corrected during construction:
  the audit script initially flagged 1,440 false-positive "overlaps"
  against `evaluation/final/data/anli-source.json` — the raw 2,400-pair ANLI
  pool this holdout's mined portion is deliberately drawn from (only 600 of
  2,400 were previously consumed; construction correctly excludes anything
  already consumed via a hash-based `seen` set built from every prior
  `nli.json`, mirroring the exact method `evaluation/final/build_nli.py`
  already used). Matching the shared source pool is not leakage; the check
  was corrected to compare only against **consumed** corpora, and the
  corrected run is the one reported above.

## Investigation set audit results

- 5,047 prior items scanned (claims, source passages, atom claims/passages
  across every verdicts.json, probe file, and NLI set in the repo).
- **Found and fixed 2 real exact-text collisions** before finalizing:
  - `A byte consists of eight bits.` (both the claim and its source
    passage) exactly matched a source passage in `evaluation/pass2/data/
    verdicts.json`.
  - `Jane Austen wrote Pride and Prejudice.` exactly matched a claim in
    `evaluation/pass2/data/verdicts.json`.

  Both are well-known, commonly-cited trivia facts independently authored
  in both corpora by coincidence, not copied — but the rule is "no exact
  claim overlap," so both were replaced outright (not merely reworded) with
  different specific facts (`A nibble consists of four bits.`;
  `Emily Bronte wrote Wuthering Heights.`) before finalizing.
- **After the fix: exact overlaps 0, near-duplicate claims (≥85% word
  Jaccard) 0, internal duplicates 0.**

## SciFact reuse

44 of the 250 investigations reuse the same `scifact-corpus.jsonl`/
`scifact-claims-dev.jsonl` source data as the old final corpus (300 total
SciFact-dev claims exist; only 50 were previously consumed). Construction
explicitly excludes every previously-used claim ID and every corpus
document ID the old corpus cited (`build_investigations.py`'s
`build_scifact_fresh`, mirroring `evaluation/final/build_verdicts.py`'s own
doc-collision-avoidance logic) — so the new 44 SciFact cases cite entirely
different underlying documents and claims from the previous 50.

## Explicit limitation (stated, not resolved)

Per the hyper-pass instructions: **semantic overlap cannot be completely
ruled out.** The hash/Jaccard audits catch exact and near-exact text reuse
reliably; they cannot catch a case that tests the *same underlying fact or
reasoning pattern* in sufficiently different wording (for example, this new
corpus and the old one both happen to include a fact about Lake Baikal's
location, phrased two different ways with two different sentence
structures and testing two different aspects — country vs. relative
location — of the same well-known geographic fact). This is disclosed
rather than hidden: common, widely-known trivia facts have a limited pool
of natural variants, and some thematic overlap of *that* specific kind is
expected and was not chased down exhaustively, since doing so would
require excluding broad categories of real-world general knowledge rather
than fixing genuine leakage. No exact or near-exact (≥85-90% word overlap)
duplicate was found or permitted to remain in either the NLI holdout or the
investigation set.
