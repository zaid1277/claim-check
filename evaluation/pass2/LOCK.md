# Pass 2 architecture lock

Locked after development, validation, ablations and 132 passing backend tests,
before opening any new held-out measurements.

Selected NLI: MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli.
Selected relevance filter: cross-encoder/ms-marco-MiniLM-L6-v2, raw score >= 2.
Retain original embedding ranking. The ranking ablation did not improve recall
or end-to-end decisions; use the cross-encoder only for eligibility of both
supporting and contradicting evidence. Replace exact subject/predicate vetoes.
Contradiction confidence remains >= .85; existing .65 NLI floor, .35 cosine floor,
source weights, .5 evidence minimum and 2x dominance remain unchanged.

Use general product-version/reporting-year context checks and date requirements
for explicit current claims or present-tense leadership roles. Do not add a
number-to-stance override: there is insufficient evidence that a safe general
comparison improves this pipeline beyond contextual checks and NLI.

No temperature scaling in production: validation-selected T=3 improved NLL but
reduced contradiction recall to .135 and decision coverage to .55. That is an
unacceptable operational regression. Do not describe abstention as calibrated.

Validation: selected system 19/20 verdicts, coverage .80. Same nine-point evidence
minimum/dominance grid all returned .95 accuracy/.80 coverage; retain original
settings. Current small-model Pass 1: .65 accuracy/.85 coverage on the same cases.
The independent ANLI challenge remains difficult and candidate precision/recall
miss aspirational targets. No claim of readiness is made before final evaluation.

The final test command uses --policy production and the selected model. All final
failures must be published. No reasoning changes may follow their inspection.
