# LoRA NLI fine-tune adapter (experiment, not adopted)

A LoRA adapter (`peft`, rank 8, alpha 16) fine-tuned on top of
`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`, trained as part of the
NLI-capability-upgrade experiment described in
[`docs/nli-upgrade-report.md`](../../../../docs/nli-upgrade-report.md).

**This adapter is not used by the production system.** It measured a real
but modest gain (+1.95 macro F1 points on a properly held-out validation
split) that didn't clear this project's adoption bar, and showed a
regression on hard cases in an end-to-end pipeline replay. It's kept here as
the artifact backing that report's claims, not as a recommended model.

- Base model: `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`
- Training corpus: `evaluation/nli-upgrade/data/train.json` (1,515 pairs;
  SciFact-train, MNLI, FEVER-NLI, and hand-authored hard negatives/contradictions)
- Validation corpus: `evaluation/nli-upgrade/data/validation.json` (380 pairs,
  never touched during training or checkpoint selection)
- Config: `training-config.json` and `training-history.json` in this
  directory record the exact hyperparameters and per-epoch metrics.
- To reproduce a standalone, loadable model from this adapter:
  `evaluation/nli-upgrade/merge_lora.py`.

Framework versions: PEFT 0.21.0.
