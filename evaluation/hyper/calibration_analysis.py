"""Group 3, phase 6-7: calibration (ECE) and class-specific threshold sweep,
computed from a saved nli-result-<model>.json's validation_rows (raw label +
confidence, pre-gating). Validation only -- never the future Hyper holdout.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def load(model_file):
    return json.loads(Path(model_file).read_text())["validation_rows"]


def expected_calibration_error(rows, label, n_bins=10):
    """ECE restricted to predictions where raw == label (i.e. "when the
    model says <label> with confidence X, how often is it actually right")."""
    subset = [r for r in rows if r["raw"] == label]
    if not subset:
        return None, []
    bins = [[] for _ in range(n_bins)]
    for r in subset:
        idx = min(int(r["confidence"] * n_bins), n_bins - 1)
        bins[idx].append(r)
    ece = 0.0
    table = []
    for i, bucket in enumerate(bins):
        if not bucket:
            continue
        mean_conf = sum(r["confidence"] for r in bucket) / len(bucket)
        accuracy = sum(1 for r in bucket if r["expected"] == label) / len(bucket)
        weight = len(bucket) / len(subset)
        ece += weight * abs(mean_conf - accuracy)
        table.append(
            {
                "bin": f"{i / n_bins:.1f}-{(i + 1) / n_bins:.1f}",
                "n": len(bucket),
                "mean_confidence": round(mean_conf, 3),
                "actual_accuracy": round(accuracy, 3),
            }
        )
    return round(ece, 4), table


def threshold_sweep(rows, label, thresholds=None):
    thresholds = thresholds or [round(0.5 + 0.05 * i, 2) for i in range(10)]
    curve = []
    for t in thresholds:
        tp = sum(
            1
            for r in rows
            if r["raw"] == label and r["confidence"] >= t and r["expected"] == label
        )
        fp = sum(
            1
            for r in rows
            if r["raw"] == label and r["confidence"] >= t and r["expected"] != label
        )
        fn = sum(
            1
            for r in rows
            if r["expected"] == label
            and not (r["raw"] == label and r["confidence"] >= t)
        )
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        curve.append(
            {
                "threshold": t,
                "precision": precision,
                "recall": recall,
                "tp": tp,
                "fp": fp,
                "fn": fn,
            }
        )
    return curve


def best_pareto_threshold(curve, min_precision):
    """Highest recall among thresholds meeting a minimum precision floor."""
    candidates = [
        c
        for c in curve
        if c["precision"] is not None and c["precision"] >= min_precision
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda c: c["recall"])


if __name__ == "__main__":
    model_file = sys.argv[1] if len(sys.argv) > 1 else None
    if not model_file:
        print("usage: calibration_analysis.py <nli-result-file.json>")
        sys.exit(1)
    rows = load(model_file)
    result = {"model_file": model_file}
    for label in ["support", "contradict", "neutral"]:
        ece, table = expected_calibration_error(rows, label)
        curve = threshold_sweep(rows, label)
        result[label] = {
            "expected_calibration_error": ece,
            "reliability_table": table,
            "threshold_curve": curve,
        }
    contradict_curve = result["contradict"]["threshold_curve"]
    result["contradict"]["pareto_at_88pct_precision"] = best_pareto_threshold(
        contradict_curve, 0.88
    )
    result["contradict"]["pareto_at_92pct_precision"] = best_pareto_threshold(
        contradict_curve, 0.92
    )
    out = Path(model_file).with_name(Path(model_file).stem + "-calibration.json")
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    print(f"\nSaved to {out}")
