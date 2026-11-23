"""Remediation pass 5, parts 2-6: multi-fold model comparison, threshold
stability, and two-signal (NLI confidence + proposition relevance)
contradiction gating -- all computed from the cached scores in results/,
entirely on the NEW 684-pair corpus (data/contradiction-corpus.json), NEVER
the Group 4 Hyper holdout (part 16)."""

import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORPUS = json.loads((ROOT / "data/contradiction-corpus.json").read_text())
BY_ID = {r["id"]: r for r in CORPUS}
RELEVANCE = {
    r["id"]: r for r in json.loads((ROOT / "results/relevance-scores.json").read_text())
}
FOLDS = sorted({r["fold"] for r in CORPUS})


def prf(rows, label):
    tp = sum(1 for r in rows if r["pred"] == label and r["gold"] == label)
    fp = sum(1 for r in rows if r["pred"] == label and r["gold"] != label)
    fn = sum(1 for r in rows if r["pred"] != label and r["gold"] == label)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1, tp, fp, fn


def macro_f1(rows):
    return (
        sum(prf(rows, label)[2] for label in ("support", "contradict", "neutral")) / 3
    )


def false_contradiction_rate(rows):
    negatives = sum(1 for r in rows if r["gold"] != "contradict")
    fps = sum(
        1 for r in rows if r["pred"] == "contradict" and r["gold"] != "contradict"
    )
    return fps / negatives if negatives else 0.0


def gated_rows(model_key, threshold, relevance_min=None):
    """Apply a confidence gate (and, if given, an additional relevance-
    corroboration requirement for contradict predictions only -- part 5's
    two-signal design) to one model's cached raw scores."""
    scores = json.loads((ROOT / f"results/nli-scores-{model_key}.json").read_text())
    rows = []
    for row in scores["rows"]:
        gold = BY_ID[row["id"]]["label"]
        fold = BY_ID[row["id"]]["fold"]
        pred = row["raw"] if row["confidence"] >= threshold else "neutral"
        if relevance_min is not None and pred == "contradict":
            rel = RELEVANCE[row["id"]]["relevance_score"]
            if rel < relevance_min:
                pred = "neutral"
        rows.append({"id": row["id"], "gold": gold, "pred": pred, "fold": fold})
    return rows


def fold_stats(rows):
    per_fold = defaultdict(list)
    for r in rows:
        per_fold[r["fold"]].append(r)
    stats = []
    for fold in FOLDS:
        fr = per_fold[fold]
        p, r, f1, tp, fp, fn = prf(fr, "contradict")
        stats.append(
            {
                "fold": fold,
                "n": len(fr),
                "contradict_precision": p,
                "contradict_recall": r,
                "contradict_f1": f1,
                "false_contradiction_rate": false_contradiction_rate(fr),
                "macro_f1": macro_f1(fr),
            }
        )
    return stats


def summarize(stats, metric):
    values = [s[metric] for s in stats]
    return {
        "mean": statistics.mean(values),
        "stdev": statistics.pstdev(values),
        "min": min(values),
        "max": max(values),
    }


def part3_model_comparison(threshold=0.65):
    print("=" * 70)
    print(f"PART 3: model comparison, uniform confidence threshold={threshold}")
    print("=" * 70)
    results = {}
    for key in ["current", "previous-base", "alternative"]:
        rows = gated_rows(key, threshold)
        stats = fold_stats(rows)
        meta = json.loads((ROOT / f"results/nli-scores-{key}.json").read_text())
        summary = {
            "model_name": meta["model_name"],
            "n_params_millions": meta["n_params_millions"],
            "peak_rss_mb": meta["peak_rss_mb"],
            "latency_ms_median": round(
                1000 * statistics.median(r["elapsed"] for r in meta["rows"]),
                1,
            ),
            "overall_macro_f1": macro_f1(rows),
            "overall_false_contradiction_rate": false_contradiction_rate(rows),
            "fold_stats": stats,
            "contradiction_precision": summarize(stats, "contradict_precision"),
            "contradiction_recall": summarize(stats, "contradict_recall"),
            "false_contradiction_rate_folds": summarize(
                stats, "false_contradiction_rate"
            ),
            "macro_f1_folds": summarize(stats, "macro_f1"),
        }
        results[key] = summary
        m, r_ = summary["macro_f1_folds"], summary["contradiction_recall"]
        p_, f_ = (
            summary["contradiction_precision"],
            summary["false_contradiction_rate_folds"],
        )
        print(f"\n--- {key} ({meta['model_name']}) ---")
        print(
            f"  params(M)={summary['n_params_millions']} "
            f"peak_rss_mb={summary['peak_rss_mb']} "
            f"latency_median_ms={summary['latency_ms_median']}"
        )
        print(f"  macro F1 mean/std across folds: {m['mean']:.3f} / {m['stdev']:.3f}")
        print(f"  contradiction P mean/std: {p_['mean']:.3f} / {p_['stdev']:.3f}")
        print(f"  contradiction R mean/std: {r_['mean']:.3f} / {r_['stdev']:.3f}")
        print(
            f"  false-contradiction-rate mean/std: {f_['mean']:.3f} / {f_['stdev']:.3f}"
        )
    return results


def part2_6_threshold_and_two_signal(model_key="current"):
    print("\n" + "=" * 70)
    print("PART 2 + 6: threshold stability sweep (no relevance gate)")
    print("=" * 70)
    threshold_results = []
    for threshold in [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]:
        rows = gated_rows(model_key, threshold)
        stats = fold_stats(rows)
        p = summarize(stats, "contradict_precision")
        r = summarize(stats, "contradict_recall")
        fcr = summarize(stats, "false_contradiction_rate")
        meets_target = p["mean"] >= 0.85 and r["mean"] >= 0.65 and fcr["mean"] <= 0.05
        no_collapse = p["min"] >= 0.70 and r["min"] >= 0.45
        threshold_results.append(
            {
                "threshold": threshold,
                "precision": p,
                "recall": r,
                "false_contradiction_rate": fcr,
                "meets_target": meets_target,
                "no_fold_collapse": no_collapse,
            }
        )
        flag = "OK" if meets_target and no_collapse else ""
        print(
            f"  t={threshold:.2f}  "
            f"P={p['mean']:.3f}(+/-{p['stdev']:.3f}, min={p['min']:.3f})  "
            f"R={r['mean']:.3f}(+/-{r['stdev']:.3f}, min={r['min']:.3f})  "
            f"FCR={fcr['mean']:.3f}(+/-{fcr['stdev']:.3f}, max={fcr['max']:.3f})  "
            f"{flag}"
        )

    print("\n" + "=" * 70)
    print("PART 5: two-signal gating sweep (confidence AND relevance corroboration)")
    print("=" * 70)
    two_signal_results = []
    for threshold in [0.60, 0.65, 0.70]:
        for relevance_min in [None, -2.0, -1.0, 0.0, 0.5, 1.0, 1.5, 2.0]:
            rows = gated_rows(model_key, threshold, relevance_min)
            stats = fold_stats(rows)
            p = summarize(stats, "contradict_precision")
            r = summarize(stats, "contradict_recall")
            fcr = summarize(stats, "false_contradiction_rate")
            meets_target = (
                p["mean"] >= 0.85 and r["mean"] >= 0.65 and fcr["mean"] <= 0.05
            )
            no_collapse = p["min"] >= 0.70 and r["min"] >= 0.45
            two_signal_results.append(
                {
                    "threshold": threshold,
                    "relevance_min": relevance_min,
                    "precision": p,
                    "recall": r,
                    "false_contradiction_rate": fcr,
                    "meets_target": meets_target,
                    "no_fold_collapse": no_collapse,
                }
            )
            flag = "OK" if meets_target and no_collapse else ""
            print(
                f"  t={threshold:.2f} rel_min={str(relevance_min):>5}  "
                f"P={p['mean']:.3f}(min={p['min']:.3f})  "
                f"R={r['mean']:.3f}(min={r['min']:.3f})  "
                f"FCR={fcr['mean']:.3f}(max={fcr['max']:.3f})  {flag}"
            )
    return threshold_results, two_signal_results


def main():
    model_comparison = part3_model_comparison()
    threshold_sweep, two_signal_sweep = part2_6_threshold_and_two_signal("current")
    out = {
        "model_comparison": model_comparison,
        "threshold_sweep": threshold_sweep,
        "two_signal_sweep": two_signal_sweep,
    }
    (ROOT / "results/fold-analysis.json").write_text(json.dumps(out, indent=2))
    print("\nWrote results/fold-analysis.json")


if __name__ == "__main__":
    main()
