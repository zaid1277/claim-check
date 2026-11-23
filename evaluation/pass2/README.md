# Reliability Pass 2 artifacts

Start with [the final reliability report](../../docs/final-reliability-report.md) —
this generation's own write-up was superseded by that report.

- `baseline/`: immutable Pass 1 source, original predictions/settings, blind
  baseline on the new corpus, and audit of previously disclosed errors.
- `data/`: ANLI provenance/sample, independently authored NLI and verdict TSVs,
  frozen JSON cases and hashes. Do not rebuild or relabel after inspecting errors.
- `METHODOLOGY.md`: splits, sampling, metric denominators and planned comparisons.
- `LOCK.md`, `lock.json`: selected policy and production code hashes recorded
  before the one final test. No subsequent reasoning changes are allowed.
- `experiment.py`: cache-aware candidate comparison; test is sealed by default.
  `--policy production` exercises the current production gate. `--policy pass1`
  requires importing the archived source; it refuses the modified pipeline.
- `calibration.py`: validation-only calibration diagnostics and temperature sweep.
- `runtime.py`: fresh NLI/embedding inference timing on validation, no web/database.
- `report.py`: saved-result comparison, every error, aspirational readiness checks.
  Exit 1 is intentional when the system misses the requested targets.
- `results/tables.md`: complete per-label metrics and confusion matrices.

The inference cache is ignored by Git. Test outputs are stored independently of
validation and development. Re-running a disclosed test is regression verification,
not a new held-out generalization claim. Do not overwrite the measured artifacts.

Example validation command, from the repository root:

```sh
HF_HUB_OFFLINE=1 api/.venv/bin/python evaluation/pass2/experiment.py \
  --model MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli \
  --policy production --split validation --output /tmp/pass2-validation.json
```

The one final test used `--split test --unlock-test --policy production` after lock.
The raw model choice was not selected against its result. Reproduce the archived
Pass 1 by extracting its source archive to a temporary directory and setting
`PYTHONPATH` to the extracted `api` directory; pass the old model explicitly.

No source claims in this corpus should be treated as a verified knowledge base.
The ANLI rows retain publisher labels; authored fixtures include fictional and
counterfactual statements. End-to-end gold concerns the supplied evidence, not an
infallible conclusion about the world. Domains and source weights are simulated.
