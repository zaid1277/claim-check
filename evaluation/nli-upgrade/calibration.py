"""NLI upgrade pass, Phase 14: calibration on NEW validation data only --
never reusing the old hand-tuned contradiction threshold automatically.
Builds a confidence histogram, a reliability curve (confidence bucket vs
actual accuracy), and a contradiction precision/recall curve across
confidence thresholds, then reports the threshold that would be chosen
if this model were adopted (informational -- not applied to production
this pass, per the "no other architecture work yet" instruction)."""

import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def reliability_curve(rows, n_buckets=10):
    buckets = defaultdict(list)
    for r in rows:
        bucket = min(n_buckets - 1, int(r["confidence"] * n_buckets))
        buckets[bucket].append(r["predicted"] == r["expected"])
    curve = []
    for b in range(n_buckets):
        items = buckets.get(b, [])
        curve.append(
            {
                "confidence_range": f"{b / n_buckets:.1f}-{(b + 1) / n_buckets:.1f}",
                "n": len(items),
                "accuracy": sum(items) / len(items) if items else None,
            }
        )
    return curve


def contradiction_curve(rows, thresholds):
    curve = []
    for t in thresholds:
        tp = fp = fn = 0
        for r in rows:
            predicted = r["predicted"] if r["confidence"] >= t else "neutral"
            if r["predicted"] != "contradict":
                predicted = r["predicted"]  # only gate contradict predictions
            if predicted == "contradict" and r["expected"] == "contradict":
                tp += 1
            elif predicted == "contradict" and r["expected"] != "contradict":
                fp += 1
            elif predicted != "contradict" and r["expected"] == "contradict":
                fn += 1
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--eval-results", required=True, help="output of evaluate_model.py"
    )
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    report = json.loads((ROOT / "results" / args.eval_results).read_text())
    rows = report["results"]

    histogram = defaultdict(int)
    for r in rows:
        histogram[round(r["confidence"], 1)] += 1

    reliability = reliability_curve(rows)
    contradiction_pr = contradiction_curve(
        rows, [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]
    )

    out = {
        "confidence_histogram": dict(sorted(histogram.items())),
        "reliability_curve": reliability,
        "contradiction_precision_recall_curve": contradiction_pr,
    }
    (ROOT / "results" / args.out).write_text(json.dumps(out, indent=2))
    print("Reliability curve:")
    for row in reliability:
        acc = f"{row['accuracy']:.3f}" if row["accuracy"] is not None else "n/a"
        print(f"  {row['confidence_range']}: n={row['n']:>4} accuracy={acc}")
    print("\nContradiction precision/recall by threshold:")
    for row in contradiction_pr:
        p = f"{row['precision']:.3f}" if row["precision"] is not None else "n/a"
        r = f"{row['recall']:.3f}" if row["recall"] is not None else "n/a"
        print(f"  t={row['threshold']:.2f} precision={p} recall={r}")
    print(f"\nWrote results/{args.out}")


if __name__ == "__main__":
    main()
