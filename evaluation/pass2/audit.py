"""Audit the disclosed Pass 1 test set before changing reasoning code."""

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
old = json.loads((ROOT / "baseline/final.json").read_text())
errors = []
for task, rows in old["predictions"].items():
    for row in rows:
        if row["split"] != "test" or task == "retrieval":
            continue
        prediction = row.get("gated", row["predicted"])
        if prediction == row["expected"]:
            continue
        if task == "nli":
            reason = row.get("exclusion_reason") or ""
            cause = (
                "entity mismatch"
                if "subject" in reason
                else "relevance error"
                if reason
                else "NLI " + row["expected"] + " error"
            )
        else:
            reasons = [
                e.get("exclusion_reason")
                for e in row["assessment"]["evidence"]
                if e.get("exclusion_reason")
            ]
            reason = "; ".join(sorted(set(reasons)))
            cause = (
                "entity mismatch"
                if "subject" in reason
                else "relevance error"
                if "predicate" in reason
                else "NLI support error"
                if prediction == "SUPPORTED"
                else "NLI contradiction error"
            )
        errors.append(
            dict(
                task=task,
                id=row["id"],
                expected=row["expected"],
                predicted=prediction,
                primary_cause=cause,
                reason=reason,
            )
        )
with (ROOT / "baseline/error-audit.csv").open("w") as f:
    w = csv.DictWriter(f, fieldnames=list(errors[0]))
    w.writeheader()
    w.writerows(errors)
missed = [
    r
    for r in old["predictions"]["nli"]
    if r["split"] == "test"
    and r["expected"] == "contradict"
    and r["gated"] != "contradict"
]
summary = {
    "error_counts": {
        task: dict(Counter(r["primary_cause"] for r in errors if r["task"] == task))
        for task in ("nli", "verdicts")
    },
    "missed_contradictions": dict(
        Counter(
            r.get("exclusion_reason") or "NLI output neutral before gate"
            for r in missed
        )
    ),
    "attribution": (
        "One primary diagnostic cause per wrong effective pair/verdict. "
        "Search/query/extraction causes cannot be measured without live search."
    ),
}
(ROOT / "baseline/error-audit.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
