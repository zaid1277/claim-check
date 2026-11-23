"""Validation-only probability diagnostics; evidence products are not probabilities."""

import argparse
import json
from pathlib import Path

import numpy as np
from experiment import CachedNLI

ROOT = Path(__file__).resolve().parent


def calibration(probabilities, gold, bins=10):
    p = np.asarray(probabilities)
    y = np.asarray(gold)
    confidence = p.max(axis=1)
    correct = p.argmax(axis=1) == y
    bucket = []
    ece = 0
    for i in range(bins):
        mask = (confidence >= i / bins) & (
            (confidence < (i + 1) / bins) if i < bins - 1 else (confidence <= 1)
        )
        if not mask.any():
            continue
        acc = float(correct[mask].mean())
        conf = float(confidence[mask].mean())
        count = int(mask.sum())
        ece += count / len(y) * abs(acc - conf)
        bucket.append(
            dict(
                lower=i / bins,
                upper=(i + 1) / bins,
                count=count,
                accuracy=acc,
                confidence=conf,
            )
        )
    target = np.eye(p.shape[1])[y]
    return dict(
        ece=ece,
        brier=float(((p - target) ** 2).sum(axis=1).mean()),
        nll=float(-np.log(np.maximum(p[np.arange(len(y)), y], 1e-12)).mean()),
        bins=bucket,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows = [
        r
        for r in json.loads((ROOT / "data/nli.json").read_text())
        if r["split"] == "validation"
    ]
    labels = ["entailment", "contradiction", "neutral"]
    gold = [["support", "contradict", "neutral"].index(r["label"]) for r in rows]
    results = {}
    for temperature in [0.7, 1.0, 1.5, 2.0, 3.0]:
        nli = CachedNLI(args.model, temperature)
        probs = [nli.probabilities(r["claim"], r["passage"]) for r in rows]
        results[str(temperature)] = calibration(
            [[p[label] for label in labels] for p in probs], gold
        )
    best = min(results, key=lambda t: results[t]["nll"])
    Path(args.output).write_text(
        json.dumps(
            dict(
                model=args.model,
                split="validation",
                by_temperature=results,
                nll_selected_temperature=float(best),
            ),
            indent=2,
        )
        + "\n"
    )
    print(args.model, best, {k: round(v["ece"], 3) for k, v in results.items()})


if __name__ == "__main__":
    main()
