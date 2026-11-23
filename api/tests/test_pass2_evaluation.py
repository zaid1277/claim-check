"""Protect frozen evaluation inputs and explicit coverage denominators."""

import hashlib
import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "evaluation/pass2"


def test_pass2_frozen_data_and_independent_tasks():
    data = ROOT / "data"
    manifest = json.loads((data / "manifest.json").read_text())
    for name, digest in manifest.items():
        assert hashlib.sha256((data / name).read_bytes()).hexdigest() == digest
    nli = json.loads((data / "nli.json").read_text())
    verdicts = json.loads((data / "verdicts.json").read_text())
    assert len(nli) == 408
    assert len(verdicts) == 100
    assert not {r["claim"] for r in nli} & {r["claim"] for r in verdicts}
    for rows in [nli, verdicts]:
        groups = {
            split: {r["group"] for r in rows if r["split"] == split}
            for split in ["development", "validation", "test"]
        }
        assert not groups["development"] & groups["validation"]
        assert not groups["development"] & groups["test"]
        assert not groups["validation"] & groups["test"]


def test_selective_accuracy_cannot_hide_abstention():
    metrics = runpy.run_path(str(ROOT / "experiment.py"))["metrics"]
    labels = ["SUPPORTED", "UNSUPPORTED", "MIXED_EVIDENCE", "INSUFFICIENT_EVIDENCE"]
    rows = [
        {"expected": "SUPPORTED", "predicted": "INSUFFICIENT_EVIDENCE"},
        {"expected": "UNSUPPORTED", "predicted": "UNSUPPORTED"},
        {"expected": "INSUFFICIENT_EVIDENCE", "predicted": "SUPPORTED"},
    ]
    result = metrics(rows, labels)
    assert result["accuracy"] == 1 / 3
    assert result["decision_coverage"] == 2 / 3
    assert result["selective_accuracy"] == 0.5
    assert result["incorrect_confident_verdict_rate"] == 1 / 3
    abstained = metrics(
        [{"expected": "SUPPORTED", "predicted": "INSUFFICIENT_EVIDENCE"}], labels
    )
    assert abstained["selective_accuracy"] is None
    assert abstained["decision_coverage"] == 0
