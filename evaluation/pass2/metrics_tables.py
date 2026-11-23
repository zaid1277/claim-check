"""Render measurements from saved predictions, without rerunning the test set."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
b = json.loads((ROOT / "baseline/new-corpus.json").read_text())["metrics"]
f = json.loads((ROOT / "results/final-test.json").read_text())["metrics"]
lines = [
    "# Pass 2 held-out tables",
    "",
    "All comparisons below use the same new test split.",
    "",
    "| Metric | Pass 1 | Pass 2 |",
    "|---|---:|---:|",
]
for name, x, y in [
    (
        "Raw NLI macro F1",
        b["nli"]["test"]["raw"]["macro_f1"],
        f["nli"]["test"]["raw"]["macro_f1"],
    ),
    (
        "Effective NLI macro F1",
        b["nli"]["test"]["macro_f1"],
        f["nli"]["test"]["macro_f1"],
    ),
    (
        "False contradiction rate",
        b["nli"]["test"]["false_contradiction_rate"],
        f["nli"]["test"]["false_contradiction_rate"],
    ),
    (
        "Verdict accuracy",
        b["verdicts"]["test"]["accuracy"],
        f["verdicts"]["test"]["accuracy"],
    ),
    (
        "Decision coverage",
        b["verdicts"]["test"]["decision_coverage"],
        f["verdicts"]["test"]["decision_coverage"],
    ),
    (
        "Abstention rate",
        b["verdicts"]["test"]["abstention_rate"],
        f["verdicts"]["test"]["abstention_rate"],
    ),
    (
        "Selective accuracy",
        b["verdicts"]["test"]["selective_accuracy"],
        f["verdicts"]["test"]["selective_accuracy"],
    ),
    (
        "Incorrect confident verdict rate",
        b["verdicts"]["test"]["incorrect_confident_verdict_rate"],
        f["verdicts"]["test"]["incorrect_confident_verdict_rate"],
    ),
    (
        "Definitive coverage",
        b["verdicts"]["test"]["definitive_coverage"],
        f["verdicts"]["test"]["definitive_coverage"],
    ),
    (
        "Definitive selective accuracy",
        b["verdicts"]["test"]["definitive_accuracy"],
        f["verdicts"]["test"]["definitive_accuracy"],
    ),
]:
    lines.append(f"| {name} | {x:.4f} | {y:.4f} |")
for name, m in [
    ("Pass 1 effective NLI", b["nli"]["test"]),
    ("Pass 2 raw NLI", f["nli"]["test"]["raw"]),
    ("Pass 2 effective NLI", f["nli"]["test"]),
    ("Pass 1 verdict", b["verdicts"]["test"]),
    ("Pass 2 verdict", f["verdicts"]["test"]),
]:
    lines += [
        "",
        f"## {name}",
        "",
        "| Label | Precision | Recall | F1 | Count |",
        "|---|---:|---:|---:|---:|",
    ]
    for label, v in m["per_label"].items():
        lines.append(
            f"| {label} | {v['precision']:.4f} | {v['recall']:.4f} | "
            f"{v['f1']:.4f} | {v['count']} |"
        )
    lines += [
        "",
        "Confusion matrix: rows expected; columns predicted; order "
        + ", ".join(m["labels"])
        + ".",
        "```json",
        json.dumps(m["confusion_matrix"]),
        "```",
    ]
lines += [
    "",
    "## Candidate comparison (validation only)",
    "",
    "| Model | Raw macro F1 | Support F1 | Contradiction F1 | Neutral F1 | "
    "Contradiction precision | Contradiction recall | Raw false contradiction rate |",
    "|---|---:|---:|---:|---:|---:|---:|---:|",
]
for name in ["small", "base", "distil"]:
    d = json.loads((ROOT / f"results/{name}-semantic-validation.json").read_text())
    m = d["metrics"]["nli"]["validation"]["raw"]
    p = m["per_label"]
    lines.append(
        f"| {d['configuration']['model']} | {m['macro_f1']:.4f} | "
        f"{p['support']['f1']:.4f} | {p['contradict']['f1']:.4f} | "
        f"{p['neutral']['f1']:.4f} | {p['contradict']['precision']:.4f} | "
        f"{p['contradict']['recall']:.4f} | {m['false_contradiction_rate']:.4f} |"
    )
(ROOT / "results/tables.md").write_text("\n".join(lines) + "\n")
