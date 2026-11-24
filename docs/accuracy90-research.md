# Accuracy improvement pass and NLI research — 23 November 2026

## Outcome

**90% overall verdict accuracy was not achieved or established.** One concrete
retrieval defect was reproduced, corrected and checked against the existing
175-case development replay. The production NLI model and thresholds remain
unchanged. This pass was wrapped up at the user's request before new candidate
model benchmarks or a fresh independent confirmation evaluation were run.

| Development replay | Before | After |
| --- | ---: | ---: |
| Correct verdicts | 133/175 (76.0%) | 134/175 (76.57%) |
| Coverage | 61.14% | 61.71% |
| Selective accuracy | 97.20% | 97.22% |
| False abstentions | 39 | 38 |
| Incorrect decided verdicts | 3 | 3 |
| Hard-case accuracy | 41/75 (54.67%) | 42/75 (56.0%) |

Only `final-scifact-143` changed: insufficient evidence became the expected
supported verdict. Although the historical data path includes `final`, this
175-case set was already reused for development in earlier passes; these
numbers are **not independent held-out results or live-web accuracy**.

Raw outputs: `evaluation/accuracy90/results/baseline-development.json` and
`candidate-development.json`. The current independent confirmation result
remains the older 150-case result in [the remediation report](remediation-final-report.md).
No existing holdout, label, source weight or threshold was altered.

## Reproduced retrieval defect and fix

The pipeline capped each domain at its first three candidate passages **before**
computing similarity. Introductory or irrelevant text could exhaust that
allowance, discarding a relevant later paragraph regardless of its relevance.
The new regression failed with INSUFFICIENT_EVIDENCE before the change.

Now the pipeline ranks the bounded candidate pool first, then walks the ranked
list, enforcing the same per-domain limit and filling the same top-K allowance
from other domains. It uses the existing embeddings and cosine score. The
change adds no model, search query or dependency and does not let one domain
contribute more selected passages. It may embed more candidates than before,
but the collection's existing maximum still bounds the work.

Tests cover both the late relevant passage and filling top-K from other sources
when a high-ranked domain reaches its allowance. API/model/database regressions
remain separate from benchmark accuracy.

## A correction to earlier diagnosis

The earlier `evaluation/accuracy-max/oracle_aggregation.py` experiment described
itself as raw NLI with all gates removed. Inspection shows that `raw_stance`
is the output of `LocalNLI.classify`, which has already applied its confidence
threshold. The experiment also retains `relevance_weight` and invokes the
normal scorer, including risk/source rules. It is a useful replay, but **not a
fully ungated model oracle or a mathematical upper bound**. Its ~80% result
must not be used to prove that higher accuracy is impossible. No corrected
oracle was run in this pass; the historical output remains preserved.

## Research shortlist

These are candidates to measure, not claimed upgrades. Model configurations were
read directly and confirmed explicit entailment, neutral and contradiction labels.

| Candidate | Why investigate | Compatibility and caution |
| --- | --- | --- |
| `tasksource/ModernBERT-large-nli` | Broad multitask NLI training, including logical and document-level tasks; a different encoder family | Three labels; downloaded revision `ca476cb923a8637073d4ceb0f19f7fc236e260d4`. Configured context limit 2048, but comparison should retain the production 512-token limit first. CPU speed and Claim Check accuracy unmeasured. |
| `sileod/deberta-v3-large-tasksource-nli` | Broader multitask training with an MNLI classification head, comparable architecture to the current model | Three labels; downloaded revision `212de447184bda8fb9415a2e5697846864ddf304`. 512-token configuration. Same-family errors may be correlated. |
| `tasksource/ModernBERT-base-nli` | Smaller resource-oriented candidate | Three labels confirmed; not downloaded or measured in this pass. |

The authors describe their training and benchmark results in the
[ModernBERT-large model card](https://huggingface.co/tasksource/ModernBERT-large-nli),
[ModernBERT-base model card](https://huggingface.co/tasksource/ModernBERT-base-nli),
and [tasksource DeBERTa model card](https://huggingface.co/sileod/deberta-v3-large-tasksource-nli).
Their benchmark numbers are not Claim Check verdict accuracy. Broad training
also makes dataset-overlap checks important before calling any evaluation unseen.

The [Laurer zeroshot-v2 model documentation](https://huggingface.co/MoritzLaurer/deberta-v3-large-zeroshot-v2.0)
specifies entailment versus not-entailment. Those binary models are **not direct
three-way NLI replacements**: not-entailment combines missing information and
contradiction. Mapping it to contradiction would reintroduce a serious stance bug.

## Research implications for the rest of the pipeline

1. **Measure retrieval independently of the verifier.** The project's older
   retrieval-oracle script uses the model's predicted direction as evidence
   correctness, which can conflate retrieval misses with NLI errors. A proper
   retrieval evaluation needs independently annotated relevant/rationale passages.
   [Chen et al., NAACL 2024](https://aclanthology.org/2024.naacl-long.196/) explicitly
   distinguish curated evidence from realistic web retrieval and evaluate a
   pipeline with fine-grained evidence retrieval. This supports measuring the
   two stages separately; it does not establish a numeric gain for this project.
2. **Preserve context around evidence.** Passage boundaries, entity scope and
   qualifiers matter. The project previously found blanket sentence-window
   selection worse, so any new context strategy must beat that baseline rather
   than assume shorter passages help.
3. **Do not assume an ensemble helps.** A recent
   [scientific-verification preprint](https://arxiv.org/abs/2611.03093) reports that
   requiring NLI/LLM agreement reduced performance relative to its stronger LLM.
   Its models, data and hardware differ from this project; this is evidence to
   test fusion, not a recommendation to copy its architecture or scores.
4. **Treat decomposition as a meaning-preservation task.**
   [FactLens](https://aclanthology.org/2025.findings-acl.929/) evaluates fine-grained
   verification and highlights context/semantic-equivalence challenges. Extend
   negation, attribution, quantifier and multi-atom coverage regressions before
   expanding automatic decomposition.

No BM25, new reranker, agent framework, generative verifier or training system
was added. Those would require separate evidence of benefit and scope decisions.

## Reproducible next comparison

`evaluation/accuracy90/compare_nli.py` is prepared and linted, but **not run** in
this wrap-up. It uses the same existing 380-pair development-validation set,
production premise/hypothesis ordering, punctuation normalization and token
limit. It separates raw labels from confidence-gated labels and records actual
model revision, data hash, median and p95 latency. Run models sequentially to
avoid keeping multiple large models in this machine's memory.

```sh
HF_HUB_OFFLINE=1 api/.venv/bin/python evaluation/accuracy90/compare_nli.py \
  --model tasksource/ModernBERT-large-nli \
  --output evaluation/accuracy90/results/modernbert-development.json
```

Also measure the current model and tasksource DeBERTa with distinct output files.
Do not claim improved verdict accuracy from pair-level F1 alone. A promising
candidate must improve the full pipeline on development data without a material
increase in confident errors, then be frozen and evaluated once on fresh,
leakage-audited cases with all four verdicts and realistic difficulty/domain mix.
Report overall accuracy, coverage, selective accuracy, false contradictions,
latency and confidence intervals. If a 90% result appears only after dropping
hard cases or reusing tuning data, it does not meet the requested goal.
