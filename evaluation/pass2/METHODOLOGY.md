# Pass 2 protocol, recorded before candidate evaluation

Pass 1 source, settings and original predictions are preserved in baseline/.
`baseline/new-corpus.json` measures that frozen implementation on the new corpus;
test predictions are saved blindly, with test output suppressed until lock.

## Data and leakage boundaries

- 408 NLI pairs: 108 authored pairs (36 proposition groups across 12 domains),
  plus 300 pairs from facebook/anli dev_r1/dev_r2/dev_r3. Publisher labels remain
  unchanged. ANLI rows are sorted by pair hash, limited to 100 per label, and
  deduplicated by premise before splitting. No inference determines selection.
- NLI split: 186 development / 111 validation / 111 held-out test. Every authored
  proposition and its three stance variants stays together. ANLI has unique
  premises across splits. Hashes and source revision are recorded.
- 100 separately authored verdict cases: 35 easy / 40 medium / 25 hard. They are
  not generated from the NLI pairs. Split within difficulty/verdict strata, sorting
  by claim hash: 49 development / 20 validation / 31 held-out test. Repeated
  linguistic patterns across cases are a limitation despite disjoint claims.
- Retrieval corpus uses those 100 end-to-end candidate pools, not NLI examples.
  Gold relevant indices concern full directional evidence. Recall is undefined
  for empty-gold/insufficient cases; means exclude them. Precision includes them.
- ANLI is an independently human-labelled challenge set, not representative live
  evidence. Some pretrained candidates trained on ANLI/FEVER train partitions;
  use of development partitions does not prove absence of training contamination.
  Authored cases are controlled relations, not independently adjudicated truth.
  Synthetic source domains exercise source weights; they are not fetched sources.
- Frozen source/dataset files are never relabelled after viewing predictions.
  The final test set is run once after architecture lock. Baseline test results
  remain blind until that time. Disclosed Pass 1 failures are diagnostic material,
  no longer a held-out set for this revision.

## Planned comparisons

Compare current small DeBERTa, cached MNLI/FEVER/ANLI base DeBERTa and original
DistilBERT on the same development/validation cases. Compare embedding-only and
MS MARCO MiniLM cross-encoder ranking, plus semantic relevance eligibility as an
alternative to exact subject/predicate matching. Do not lower the .85 contradiction
floor to recover recall. A limited validation sensitivity grid may assess relevance
cutoffs (-2, 0, 2), minimum evidence (.3, .5, .7) and dominance (1.5, 2, 3).
Prefer existing settings unless accuracy/coverage support a change.

Report raw and effective stance separately. Coverage = proportion with any verdict
other than INSUFFICIENT_EVIDENCE; mixed counts as a decision. Also report definitive
coverage/accuracy for SUPPORTED/UNSUPPORTED only. Selective accuracy conditions on
non-abstention. Incorrect confident verdict rate means wrong non-abstaining verdicts
per all cases, not a calibrated confidence claim. Report each verdict's precision
and recall, not only accuracy.

## Calibration and runtime

Measure top-label ECE, Brier score and negative log likelihood on validation.
Fit a temperature only on validation and retain it only if system decisions justify
it. Evidence scores are weighted scores, not probabilities; no verdict confidence
exists. Candidate experiment timings include cache hits and cannot be latency
comparisons. Use separate warm uncached measurements for selected runtime claims.

## Release judgment

Targets in the user request are aspirational; report each independently and all
coverage/recall regressions. Passing a relative comparison does not make this a
production verifier. Diagnose every easy final failure; do not patch those cases
on the disclosed test set. If targets remain unmet, say so and retain the evidence.

Source: https://huggingface.co/datasets/facebook/anli (see recorded revision)
Reranker: https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2
