"""Render saved measurements and exhaustive error rows; never relabel benchmark data."""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    reports = {
        name: json.loads((ROOT / f"results/{name}.json").read_text())
        for name in ("baseline", "final")
    }
    baseline, final = (reports[n]["metrics"] for n in ("baseline", "final"))
    b, f = baseline["nli"]["test"], final["nli"]["test"]
    gate = {
        "raw_nli_macro_f1_improved": f["macro_f1"] > b["macro_f1"],
        "verdict_accuracy_improved": final["verdicts"]["test"]["accuracy"]
        > baseline["verdicts"]["test"]["accuracy"],
        "gated_false_contradiction_not_worse": f["gated"]["false_contradiction_rate"]
        <= b["false_contradiction_rate"],
        "gated_contradiction_precision_not_worse": f["gated"]["per_label"][
            "contradict"
        ]["precision"]
        >= b["per_label"]["contradict"]["precision"],
    }
    (ROOT / "results/quality-gate.json").write_text(
        json.dumps(
            {
                "checks": gate,
                "passed": all(gate.values()),
                "scope": (
                    "Small controlled held-out corpus, "
                    "not a production-readiness certification."
                ),
            },
            indent=2,
        )
        + "\n"
    )
    errors = []
    for version, report in reports.items():
        for task, rows in report["predictions"].items():
            originals = {
                r["id"]: r for r in json.loads((ROOT / f"data/{task}.json").read_text())
            }
            for row in rows:
                variants = (
                    ["predicted", "gated"]
                    if task == "nli" and version == "final"
                    else ["predicted"]
                )
                if task == "retrieval":
                    if row["addressing5"] < 1:
                        errors.append(
                            [
                                version,
                                task,
                                row["split"],
                                row["id"],
                                "relevance false positive",
                                "relevant passages only",
                                str(row["indices"]),
                                originals[row["id"]]["claim"],
                                (
                                    "Recall may be perfect while top five "
                                    "include unrelated evidence."
                                ),
                            ]
                        )
                    continue
                for variant in variants:
                    if row[variant] == row["expected"]:
                        continue
                    category = (
                        "NLI false " + row[variant]
                        if task == "nli" and row[variant] != "neutral"
                        else "NLI missed directional evidence"
                    )
                    detail = row.get("exclusion_reason") or ""
                    if task == "verdicts":
                        evidence = row["assessment"]["evidence"]
                        excluded = [
                            e.get("exclusion_reason")
                            for e in evidence
                            if e.get("exclusion_reason")
                        ]
                        category = (
                            "evidence eligibility / aggregation"
                            if excluded
                            else "NLI / evidence sufficiency"
                        )
                        detail = "; ".join(sorted(set(excluded))) or (
                            "Inspect saved assessment and supplied sources; "
                            "attribution is provisional."
                        )
                    errors.append(
                        [
                            version,
                            task + (" after gate" if variant == "gated" else ""),
                            row["split"],
                            row["id"],
                            category,
                            row["expected"],
                            row[variant],
                            originals[row["id"]]["claim"],
                            detail,
                        ]
                    )
    with (ROOT / "results/errors.csv").open("w") as out:
        writer = csv.writer(out)
        writer.writerow(
            [
                "version",
                "stage",
                "split",
                "id",
                "failure_category",
                "expected",
                "actual",
                "claim",
                "diagnostic",
            ]
        )
        writer.writerows(errors)
    lines = [
        "# Held-out measurements",
        "",
        "| Metric | Baseline | Final |",
        "|---|---:|---:|",
    ]
    values = [
        ("Raw NLI macro F1", b["macro_f1"], f["macro_f1"]),
        (
            "Raw support precision",
            b["per_label"]["support"]["precision"],
            f["per_label"]["support"]["precision"],
        ),
        (
            "Raw contradiction precision",
            b["per_label"]["contradict"]["precision"],
            f["per_label"]["contradict"]["precision"],
        ),
        (
            "Raw neutral precision",
            b["per_label"]["neutral"]["precision"],
            f["per_label"]["neutral"]["precision"],
        ),
        (
            "Raw false contradiction rate",
            b["false_contradiction_rate"],
            f["false_contradiction_rate"],
        ),
        (
            "Effective contradiction precision",
            b["per_label"]["contradict"]["precision"],
            f["gated"]["per_label"]["contradict"]["precision"],
        ),
        (
            "Effective contradiction recall",
            b["per_label"]["contradict"]["recall"],
            f["gated"]["per_label"]["contradict"]["recall"],
        ),
        (
            "Effective false contradiction rate",
            b["false_contradiction_rate"],
            f["gated"]["false_contradiction_rate"],
        ),
        (
            "Recall@5",
            baseline["retrieval"]["test"]["recall5"],
            final["retrieval"]["test"]["recall5"],
        ),
        (
            "Recall@10",
            baseline["retrieval"]["test"]["recall10"],
            final["retrieval"]["test"]["recall10"],
        ),
        (
            "Addressing proportion@5",
            baseline["retrieval"]["test"]["addressing5"],
            final["retrieval"]["test"]["addressing5"],
        ),
        (
            "Verdict accuracy",
            baseline["verdicts"]["test"]["accuracy"],
            final["verdicts"]["test"]["accuracy"],
        ),
    ]
    for d in ("easy", "medium", "difficult"):
        values.append(
            (
                d + " verdict accuracy",
                baseline["verdicts"]["test"]["by_difficulty"][d],
                final["verdicts"]["test"]["by_difficulty"][d],
            )
        )
    for name, a, z in values:
        lines.append(f"| {name} | {a:.4f} | {z:.4f} |")
    lines += [
        "",
        (
            "Raw labels mean LocalNLI output after its existing 0.65 confidence floor. "
            "Effective pair labels additionally use the production eligibility gate, "
            "without decomposition or retrieval. Full verdict tests use both."
        ),
        "",
        "## Confusion matrices",
        "Rows are expected, columns predicted.",
    ]
    for name, report in reports.items():
        for task in ("nli", "verdicts"):
            m = report["metrics"][task]["test"]
            lines += [
                "",
                f"{name} {task}; order: " + ", ".join(m["labels"]),
                "```json",
                json.dumps(m["confusion_matrix"]),
                "```",
            ]
    (ROOT / "results/metrics.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(gate))
    if not all(gate.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
