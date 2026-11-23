# Final product reliability protocol

Pass 2 is frozen in baseline/pass2-source.tar.gz with hashes, resolved settings,
model/configuration records and all prior predictions/results. New measurements
must distinguish controlled reasoning, product workflow completion, extraction
quality and live-web observations. They are not interchangeable accuracy claims.

## Separation

Earlier disclosed cases are development material only. New validation cases may
inform architecture choices. Final pair/claim labels and predictions remain sealed
after dataset construction until the code/model/settings/query lock. A blind Pass 2
baseline can save final predictions without displaying them. The locked candidate
is evaluated once; all failures stay in the results. No post-test reasoning patches.

## Planned final products

- At least 500 balanced NLI pairs, with a substantial new held-out partition.
  Exclude all prior benchmark premises/claims; supplement independent public data
  with documented adversarial cases and text-quality variations.
- At least 150 distinct held-out claim investigations (40 easy, 60 medium, 50 hard),
  independent of NLI pairs. Development and validation are additional cases.
- Controlled full-product runs use real extraction, models, API, PostgreSQL,
  report retrieval/sharing and browser rendering. Search/evidence fixtures are
  explicitly identified; they must not be described as live discovery.
- At least 50 typed runs; 25 fixed public URLs; 20 pasted articles; 20 readable OCR
  images; 10 same-claim four-route consistency probes. Cross-modal repetitions do
  not inflate the distinct factual-claim denominator.
- URL extraction completion and proposal usability are measured separately. Manual
  review of proposals may annotate usability; it cannot relabel verdicts after
  predictions. Unreviewed output must not be called extraction precision.
- OCR has exact source transcripts and measured CER/WER before correction. Corrected
  text must be what the investigation consumes. Raw OCR accuracy, corrected-text
  reasoning accuracy and completion are reported separately.
- At least 50 compound stress sentences plus numerical, time, entity collision,
  copying, conflict and absent-evidence probes. Conservative non-decomposition can
  be correct for OR/causation/ambiguous context; report coverage and correctness.
- Sixty frozen live claims (20 per difficulty) run after lock. They are LIVE-WEB
  OBSERVATIONS unless independent gold verification is available. Failed URLs,
  searches and extractions remain in denominators, never replaced by easier cases.

## Metrics

Report raw and effective stance precision/recall/F1 and confusion matrices.
Non-abstention includes mixed; also report definitive-only coverage/accuracy.
Report false abstention, correct abstention, incorrect non-abstaining verdicts,
latency median/p95 by route, failures, source evidence and resource use. Search
ranking recall on supplied evidence does not establish live retrieval recall.

## Selection and release

No blanket threshold reduction or fact-specific rules. Evaluate structured checks
only for aligned propositions and directly comparable values. Revisit the model
only if error analysis supports it. Source deduplication and temporal context must
not turn copied or outdated evidence into independent current confirmation.

All user targets are explicit readiness checks. Publish unmet targets; do not
substitute passing tests or workflow completion for factual reliability. Keep the
application understandable and runnable. No deployment or publication is implied
by this release evaluation; public-share functionality is tested using test reports.
