# Hyper pass — Phase 1 & 2: false-abstention analysis and aggregation audit

No code was changed to produce this document. All data comes from the already
completed, locked final evaluation (`evaluation/final/results/`), which is now
treated as development evidence per the pass-4 instructions. The old final
evaluation directory is untouched.

## Phase 2 — exact current aggregation logic (as documented, for reference)

Source: `api/app/services/evidence_scoring.py`, `api/app/services/pipeline.py`.

```
evidence_score = similarity * stance_confidence * source_weight   # per passage

# Eligibility (pipeline.gate_stance), applied before scoring:
#   - temporal_exclusion: claims needing "current" evidence require a recent
#     published_at (window: current_evidence_days = 365)
#   - context_exclusion: deterministic context/quote-attribution heuristic
#   - proposition relevance: relevance_score(claim, passage) < 2.0 -> excluded
#   - contradiction-specific: stance == contradict and confidence < 0.85 -> excluded
#   (any exclusion demotes stance to "neutral" and it stops counting)
#
# Separately, in nli.interpret_label, BEFORE the above:
#   - any label (entailment/contradiction) with confidence < min_nli_confidence
#     (0.65) is already collapsed to "neutral" -- invisible after the fact.

# Independence de-duplication (evidence_scoring.assess), applied per claim:
#   - evidence sorted by evidence_score descending
#   - at most ONE retained item per (independence_group, stance) pair
#   - independence_group = registrable domain (source_group)
#   - a second same-stance item from the same domain, or near-duplicate
#     content (>=90% word-Jaccard) from any domain, is discarded

support_total    = sum(evidence_score of retained items where stance=="support")
contradict_total = sum(evidence_score of retained items where stance=="contradict")

# Final verdict (evidence_scoring.aggregate):
if support_total + contradict_total < minimum_evidence (0.5):
    INSUFFICIENT_EVIDENCE
elif support_total >= dominance_ratio (2.0) * contradict_total:
    SUPPORTED
elif contradict_total >= dominance_ratio (2.0) * support_total:
    UNSUPPORTED
else:
    MIXED_EVIDENCE

# For multi-atom (compound) claims (pipeline.check_claim):
if any atom UNSUPPORTED:      whole claim UNSUPPORTED
elif any atom MIXED_EVIDENCE: whole claim MIXED_EVIDENCE
elif all atoms SUPPORTED:     whole claim SUPPORTED
else:                         whole claim INSUFFICIENT_EVIDENCE  # even 3/4 supported
```

Source weights (`api/app/core/settings.py`):

| Category | Weight | Matched by |
|---|---:|---|
| research | 1.00 | nature.com, science.org |
| official | 0.95 | listed domains, or any `.gov`/`.gov.uk` |
| institution | 0.90 | listed domains, or any `.edu` |
| reporting | 0.75 | reuters.com, apnews.com, bbc.com |
| general | 0.55 | everything else, **including wikipedia.org** |
| unknown | 0.30 | blogspot.com, substack.com |

Other thresholds in force: `min_similarity` 0.35, `top_k` 10, `min_proposition_relevance`
2.0 (raw cross-encoder score), `min_nli_confidence` 0.65, `min_contradiction_confidence`
0.85, `duplicate_similarity` 0.9, `max_atomic_claims` 4.

## Phase 1 — false-abstention deep analysis (95 cases)

Every one of the 95 false abstentions from the locked final controlled run was
pulled with full evidence detail (`evaluation/hyper/false-abstention-analysis.json`
has all 95, in full, including per-passage similarity/stance/confidence/source
weight/exclusion reason/evidence score). Classification method: deterministic,
derived directly from the stored per-passage fields (not eyeballed), using the
priority order: atomic-coverage mismatch → excluded-directional-evidence reason
→ no-directional-NLI-signal → minimum-evidence-threshold shortfall (further
split into single-source vs. source-weight-limited vs. plain shortfall) →
dominance-ratio miss.

| Subtype | Count | % | Meaning |
|---|---:|---:|---|
| **H: single independent source only** | **57** | **60.0%** | Exactly one source cleared eligibility+dedup; alone, its `evidence_score` fell short of the 0.5 minimum-evidence cliff |
| J: no directional NLI signal survived | 15 | 15.8% | Every retrieved passage's stance was neutral after NLI+gating; cannot distinguish "genuinely neutral" from "sub-0.65-confidence support/contradict" from the stored trace — see limitation below |
| B: relevance gate excluded directional evidence | 14 | 14.7% | A support/contradict passage existed but its cross-encoder relevance score fell below 2.0 |
| D: independence/duplicate pruning | 6 | 6.3% | A second same-stance passage from the same registrable domain (or near-duplicate text) was discarded |
| Temporal filter | 1 | 1.1% | Excluded for lacking a sufficiently recent publish date |
| Contradiction eligibility (0.85 gate) | 1 | 1.1% | A contradiction was found but below the stricter contradiction-confidence gate |
| F: dominance ratio not met (MIXED-shaped case) | 1 | 1.1% | Support and contradict totals were both present and neither dominated 2:1 |

By difficulty: the dominant H-bucket is **spread evenly across all three
tiers** (16 easy / 24 medium / 17 hard) — it is a pervasive miscalibration, not
a hard-case-specific one. J and B are concentrated almost entirely in hard
cases (15 and 14 of the 95, all hard) — consistent with hard cases needing
more of the retrieval/relevance/NLI stack to work correctly.

### Sensitivity analysis on the H-bucket (57 cases) — Phase 2's requested "what if"

The 57 single-source totals are clustered just under the 0.5 cliff (median
0.458, max 0.500, min 0.294) — this is not a case of "no evidence," it is
evidence that is real but discounted by the multiplicative formula and then
capped at exactly one passage per source by the independence rule.

| If `minimum_evidence` were lowered to... | Cases that would flip |
|---:|---:|
| 0.45 | 32/57 (56%) |
| 0.40 | 43/57 (75%) |
| 0.35 | 51/57 (89%) |
| 0.30 | 56/57 (98%) |
| 0.25 | 57/57 (100%) |

Separately: **all 57** of these cases' lone counted passage has
`source_type == "general"` (weight 0.55) — in this fixture benchmark that is
the placeholder domain the harness generates for controlled documents, but the
*mechanism* generalizes directly to production: any claim whose only usable
evidence comes from an uncategorized general-web domain — **including
Wikipedia, which is not in `source_domains` and defaults to "general"** — hits
the same ceiling. Simulating a `general` weight raise from 0.55 to 0.80 alone
(no change to `minimum_evidence`) flips **51/57 (89%)** of these cases without
touching similarity, NLI, or the dominance ratio at all.

**Both levers move almost the same 89-98% of this bucket independently.**
Neither is a blind threshold hack in isolation — each is answering one of the
Phase 5 questions directly: *"does one high-quality source count sufficiently
for straightforward facts?"* (currently: no, by a wide and mechanical margin)
and *"is Wikipedia treated appropriately?"* (currently: no — it is weighted
identically to an arbitrary unclassified website).

### Limitation on subtype J (no evidence available on this)

15 hard-case false abstentions have zero surviving directional evidence. The
stored trace cannot distinguish "the NLI model genuinely called every passage
neutral" from "the NLI model called something support/contradict below the
0.65 confidence gate, which `interpret_label` already collapsed to neutral
before storing it" — that pre-gate label is never persisted. Phase 9's
per-pair contradiction analysis (missed_contradiction_categories: 57 NLI
misprediction / 8 relevance / 5 confidence / 1 temporal, from the *NLI-pair*
holdout, a different dataset) suggests the model-error component is real and
sizeable, but this specific 15-case bucket needs either re-running with an
instrumented NLI call (to log the pre-gate label) or manual reading of the 15
claim/passage pairs to resolve further.

## What this rules out

- **Not primarily a "replace the NLI model" problem.** Only 1 of 95 false
  abstentions is cleanly attributable to the contradiction-confidence gate,
  and subtype J (NLI-adjacent) is 15.8% — real, but not the majority.
- **Not primarily a retrieval-failure problem** for this bucket: none of the
  95 false abstentions had empty evidence lists (retrieval-empty was not
  observed among false abstentions in this run — cases with genuinely empty
  retrieval were correctly tagged `empty-retrieval` and expected
  `INSUFFICIENT_EVIDENCE`, i.e. correct abstentions, not false ones).
- **It is, decisively, an aggregation/source-weighting calibration problem**:
  60% of all false abstentions come from one identifiable, narrow mechanism
  (single-source evidence discounted below a fixed cliff by a multiplicative
  formula), confirming the user's own reading of the 69%
  aggregation/source-weight root-cause bucket from the locked evaluation.
