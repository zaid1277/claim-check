"""NLI upgrade pass, Phase 15: 5-fold robustness of the selected model.

Rather than retraining 5 times (hardware-infeasible in this session -- a
single 4-epoch run already takes roughly an hour on this machine, see
docs/nli-upgrade-report.md phase 6), this evaluates the ALREADY-TRAINED
adapter (or the baseline model) across 5 disjoint folds of the combined
train+validation pool, reporting mean/std/worst-fold -- a robustness
check on evaluation data composition, not on training-run variance. This
is disclosed explicitly as a scope limitation, not hidden.
"""

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "api"))
ROOT = Path(__file__).resolve().parent

from evaluate_model import classify_all, load_base, load_lora, summarize  # noqa: E402


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def make_folds(rows, n_folds=5):
    by_label = {}
    for r in rows:
        by_label.setdefault(r["label"], []).append(r)
    folds = [[] for _ in range(n_folds)]
    for group in by_label.values():
        group = sorted(group, key=lambda r: digest(r["id"]))
        for i, r in enumerate(group):
            folds[i % n_folds].append(r)
    return folds


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--lora", action="store_true")
    parser.add_argument("--max-length", type=int, default=384)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    train = json.loads((ROOT / "data/train.json").read_text())
    validation = json.loads((ROOT / "data/validation.json").read_text())
    pool = train + validation
    folds = make_folds(pool)
    print(f"Pool size: {len(pool)}, 5 folds of ~{len(pool) // 5} each")

    if args.lora:
        tokenizer, model, id2label, max_length = load_lora(args.model)
    else:
        tokenizer, model, id2label = load_base(args.model)
        max_length = args.max_length

    fold_results = []
    for i, fold in enumerate(folds):
        results, _ = classify_all(tokenizer, model, id2label, fold, max_length)
        summary = summarize(results, name=f"fold-{i}")
        fold_results.append(summary)
        print(f"fold {i}: n={summary['n']} macro_f1={summary['macro_f1']:.4f}")

    def agg(values):
        return {
            "mean": statistics.mean(values),
            "stdev": statistics.pstdev(values),
            "worst": min(values),
        }

    report = {
        "n_folds": len(folds),
        "fold_results": fold_results,
        "macro_f1": agg([f["macro_f1"] for f in fold_results]),
        "support_f1": agg([f["per_label"]["support"]["f1"] for f in fold_results]),
        "contradict_precision": agg(
            [f["per_label"]["contradict"]["precision"] for f in fold_results]
        ),
        "contradict_recall": agg(
            [f["per_label"]["contradict"]["recall"] for f in fold_results]
        ),
        "neutral_f1": agg([f["per_label"]["neutral"]["f1"] for f in fold_results]),
    }
    (ROOT / "results" / args.out).write_text(json.dumps(report, indent=2))
    m = report["macro_f1"]
    msg = f"mean={m['mean']:.4f} stdev={m['stdev']:.4f} worst={m['worst']:.4f}"
    print(f"\nmacro_f1: {msg}")
    print(f"Wrote results/{args.out}")


if __name__ == "__main__":
    main()
