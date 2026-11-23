"""Add pre-inference text-quality probes; keep all variants of a claim together."""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "data"
rows = [
    r for r in json.loads((ROOT / "nli.json").read_text()) if r["origin"] != "authored"
]
for i, row in enumerate(
    csv.DictReader((ROOT / "pair-probes.tsv").open(), delimiter="\t")
):
    for label in ["support", "contradict", "neutral"]:
        passage = row[label]
        tag = row["tags"]
        if i == 0:
            passage = (
                "Home | Site map | Contact\n"
                + passage
                + "\nReferences: Annual survey; Archive index."
            )
            tag += ",headings,navigation,references"
        if i == 2:
            passage = passage.replace("measured", "measurcd").replace(
                "measurement", "measuremcnt"
            )
            tag += ",OCR-noise"
        if i == 5:
            passage = (
                (
                    "The archive provides background information about "
                    "unrelated projects and lists administrative contacts. "
                )
                * 65
            ) + passage
            tag += ",long,truncation-risk"
        if i == 8:
            passage = (
                "[1] Competition report.\n"
                + passage
                + "\n[2] Results archive, accessed 2026."
            )
            tag += ",citation-fragments"
        rows.append(
            dict(
                id=f"final-probe-{i:02}-{label}",
                group=f"final-probe-{i:02}",
                split="test",
                domain=row["domain"],
                tag=tag,
                claim=row["claim"],
                passage=passage,
                label=label,
                published_at=None,
                origin="authored",
            )
        )
(ROOT / "nli.json").write_text(json.dumps(rows, indent=2) + "\n")
print(
    "NLI pairs:",
    len(rows),
    "; final partition:",
    sum(r["split"] == "test" for r in rows),
)
