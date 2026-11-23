"""Report the locked test once; fail aspirational readiness checks transparently."""

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from experiment import metrics

ROOT = Path(__file__).resolve().parent


def main():
    baseline = json.loads((ROOT / "baseline/new-corpus.json").read_text())
    final = json.loads((ROOT / "results/final-test.json").read_text())
    nli = final["metrics"]["nli"]["test"]
    verdicts = final["metrics"]["verdicts"]["test"]
    lock = json.loads((ROOT / "lock.json").read_text())
    repository = ROOT.parents[1]
    assert all(
        hashlib.sha256((repository / name).read_bytes()).hexdigest() == digest
        for name, digest in lock["code_sha256"].items()
    ), "Reasoning code changed after lock"
    checks = {
        "raw_nli_macro_f1_at_least_085": nli["raw"]["macro_f1"] >= 0.85,
        "contradiction_precision_at_least_090": nli["per_label"]["contradict"][
            "precision"
        ]
        >= 0.9,
        "contradiction_recall_at_least_075": nli["per_label"]["contradict"]["recall"]
        >= 0.75,
        "false_contradiction_rate_at_most_003": nli["false_contradiction_rate"] <= 0.03,
        "easy_accuracy_at_least_090": verdicts["by_difficulty"]["easy"]["accuracy"]
        >= 0.9,
        "medium_accuracy_at_least_080": verdicts["by_difficulty"]["medium"]["accuracy"]
        >= 0.8,
        "overall_accuracy_at_least_080": verdicts["accuracy"] >= 0.8,
        "hard_accuracy_at_least_065": verdicts["by_difficulty"]["hard"]["accuracy"]
        >= 0.65,
    }
    errors = []
    manual = {
        "e2e-084": (
            "relevance error",
            "The relevance score rejects an explicit counterexample.",
        ),
        "e2e-091": (
            "NLI contradiction error",
            "Unestablished causation is classified as disproof.",
        ),
        "e2e-093": (
            "entity mismatch",
            "A music group and a literature-prize claim are conflated.",
        ),
        "e2e-098": (
            "claim decomposition",
            "Coordinated predicates remain unsplit; "
            "partial passages never establish the conjunction.",
        ),
    }
    for name, report in [("pass1", baseline), ("pass2", final)]:
        for task in ["nli", "verdicts"]:
            for row in report["predictions"][task]:
                if row["split"] != "test" or row["predicted"] == row["expected"]:
                    continue
                detail = row.get("reason") or ""
                if task == "nli":
                    if row["raw"] != row["expected"]:
                        cause = {
                            "support": "NLI support error",
                            "contradict": "NLI contradiction error",
                            "neutral": "NLI neutral error",
                        }[row["raw"]]
                    elif "subject" in detail:
                        cause = "entity mismatch"
                    elif "period" in detail or "version" in detail:
                        cause = "temporal mismatch"
                    elif "confidence" in detail:
                        cause = "NLI neutral error"
                    else:
                        cause = "relevance error"
                elif name == "pass2":
                    cause, detail = manual[row["id"]]
                else:
                    reasons = [
                        e.get("exclusion_reason")
                        for e in row["assessment"]["evidence"]
                        if e.get("exclusion_reason")
                    ]
                    detail = "; ".join(sorted(set(reasons)))
                    if "subject" in detail:
                        cause = "entity mismatch"
                    elif "predicate" in detail:
                        cause = "relevance error"
                    elif row["predicted"] == "SUPPORTED":
                        cause = "NLI support error"
                    elif row["predicted"] == "UNSUPPORTED":
                        cause = "NLI contradiction error"
                    else:
                        cause = "insufficient evidence"
                errors.append(
                    dict(
                        system=name,
                        task=task,
                        id=row["id"],
                        difficulty=row["difficulty"],
                        claim=row["claim"],
                        expected=row["expected"],
                        predicted=row["predicted"],
                        primary_cause=cause,
                        diagnostic=detail,
                    )
                )
    with (ROOT / "results/errors.csv").open("w") as out:
        writer = csv.DictWriter(out, fieldnames=list(errors[0]))
        writer.writeheader()
        writer.writerows(errors)
    error_counts = {
        system: {
            task: dict(
                Counter(
                    r["primary_cause"]
                    for r in errors
                    if r["system"] == system and r["task"] == task
                )
            )
            for task in ["nli", "verdicts"]
        }
        for system in ["pass1", "pass2"]
    }
    numerical = {}
    for name, report in [("pass1", baseline), ("pass2", final)]:
        numerical[name] = {}
        for task in ["nli", "verdicts"]:
            rows = [
                r
                for r in report["predictions"][task]
                if r["split"] == "test" and re.search(r"\d", r["claim"])
            ]
            labels = (
                ["support", "contradict", "neutral"]
                if task == "nli"
                else [
                    "SUPPORTED",
                    "UNSUPPORTED",
                    "MIXED_EVIDENCE",
                    "INSUFFICIENT_EVIDENCE",
                ]
            )
            numerical[name][task] = metrics(rows, labels)
    summary = dict(
        readiness_targets=checks,
        ready=all(checks.values()),
        baseline=baseline["metrics"],
        final=final["metrics"],
        error_counts=error_counts,
        numeric_date_proxy=numerical,
        numeric_date_definition="Digit-containing claims; incomplete proxy.",
        easy_final_failures=[
            r
            for r in errors
            if r["system"] == "pass2"
            and r["task"] == "verdicts"
            and r["difficulty"] == "easy"
        ],
        test_policy="Locked system; no reasoning changes after final test.",
    )
    (ROOT / "results/report.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(
        json.dumps(
            {
                "targets": checks,
                "error_counts": error_counts,
                "numeric_date": {
                    s: {t: (v["count"], v["accuracy"]) for t, v in groups.items()}
                    for s, groups in numerical.items()
                },
            }
        )
    )
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
