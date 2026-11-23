"""Development-only failure attribution and conservative numeric-assistance trial."""

import csv
import json
import re
from pathlib import Path

from app.services.propositions import decompose_claim

ROOT = Path(__file__).resolve().parent


def aligned_number(claim, passage):
    # Exact surface frame deliberately rejects extra dates, qualifiers and entities.
    # This is an experiment, not a production override or a calibrated confidence.
    number = r"(?<!\w)[+-]?\d+(?:\.\d+)?(?!\w)"
    a, b = re.findall(number, claim), re.findall(number, passage)

    def normalize(text):
        return " ".join(text.casefold().rstrip(". ").split())

    return (
        len(a) == len(b) == 1
        and a != b
        and normalize(re.sub(number, "<value>", claim))
        == normalize(re.sub(number, "<value>", passage))
    )


pairs = {
    r["id"]: r
    for r in json.loads((ROOT / "data/nli.json").read_text())
    if r["split"] != "test"
}
report = {}
for split in ["development", "validation"]:
    results = json.loads((ROOT / f"results/{split}-base.json").read_text())[
        "predictions"
    ]["nli"]
    failures = []
    activations = []
    for row in results:
        original = pairs[row["id"]]
        if aligned_number(original["claim"], original["passage"]):
            activations.append(
                dict(id=row["id"], label=row["expected"], original=row["predicted"])
            )
        if row["expected"] == "contradict" and row["predicted"] != "contradict":
            reason = row["reason"] or ""
            category = (
                "NLI prediction/confidence"
                if row["raw"] != "contradict"
                else "relevance filter"
                if "relevance" in reason.lower()
                else "temporal filter"
                if any(
                    x in reason.lower() for x in ["year", "version", "date", "current"]
                )
                else "NLI confidence"
                if "confidence" in reason.lower()
                else "other eligibility filter"
            )
            failures.append(dict(row, passage=original["passage"], category=category))
    report[split] = dict(
        missed_contradictions=failures, numeric_activations=activations
    )
rows = []
for row in csv.DictReader((ROOT / "data/compound.tsv").open(), delimiter="\t"):
    actual = decompose_claim(row["claim"])
    expected = row["atoms"].split("|")
    rows.append(
        dict(
            claim=row["claim"],
            expected=expected,
            actual=actual,
            correct=actual == expected,
        )
    )
report["compound_development"] = dict(
    count=len(rows), correct=sum(r["correct"] for r in rows), rows=rows
)
report["decision"] = (
    "Numeric assistance is not installed: exact-frame "
    "coverage is reported, and a broader value extractor "
    "would require independent entity, predicate, unit and "
    "scope validation. Location/entity/negation/ranking "
    "overrides lack such validated alignment; no production "
    "override is justified by this trial."
)
(ROOT / "results/development-audit.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print(
    {
        s: {
            "missed": len(report[s]["missed_contradictions"]),
            "numeric_activations": len(report[s]["numeric_activations"]),
        }
        for s in ["development", "validation"]
    }
)
print(
    "Compound exact agreement:",
    report["compound_development"]["correct"],
    "/",
    len(rows),
)
