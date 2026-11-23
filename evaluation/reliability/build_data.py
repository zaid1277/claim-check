"""Build frozen, group-disjoint controlled corpora; no model predictions are used."""

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
rows = list(csv.DictReader((ROOT / "data/propositions.tsv").open(), delimiter="\t"))
nli, retrieval, verdicts = [], [], []
for i, row in enumerate(rows):
    group = f"p{i:03}"
    # Hold out whole proposition families, not punctuation/paraphrase variants.
    split = ("development", "development", "validation", "development", "test", "test")[
        (i % 6 + i // 6) % 6
    ]
    meta = {k: row[k] for k in ("domain", "difficulty", "tag")}
    meta.update(group=group, split=split)
    for stance in ("support", "contradict", "neutral"):
        nli.append(
            dict(
                meta,
                id=f"{group}-{stance}",
                claim=row["claim"],
                passage=row[stance],
                label=stance,
            )
        )
    nli.append(
        dict(
            meta,
            id=f"{group}-punctuation",
            claim=row["claim"].rstrip("."),
            passage=row["support"],
            label="support",
            tag="punctuation_variation",
        )
    )
    # Scraped surrounding text is explicitly authored noise, not a real web page.
    noisy = (
        "Menu. Subscribe. Site navigation. "
        + row["support"]
        + " Contact us. All rights reserved."
    )
    nli.append(
        dict(
            meta,
            id=f"{group}-noise",
            claim=row["claim"],
            passage=noisy,
            label="support",
            tag="noisy_scraped_text",
        )
    )
    if i % 3 == 0:
        nli.append(
            dict(
                meta,
                id=f"{group}-long",
                claim=row["claim"],
                passage=(
                    "The publication has an editorial board and a contact address. "
                    * 55
                )
                + row["support"],
                label="support",
                tag="long_passage",
            )
        )
    passages = [row["support"], row["contradict"], row["neutral"]]
    passages += [rows[(i + j) % len(rows)]["neutral"] for j in range(1, 13)]
    retrieval.append(
        dict(meta, id=group, claim=row["claim"], passages=passages, relevant=[0, 1])
    )
    expected = ("SUPPORTED", "UNSUPPORTED", "MIXED_EVIDENCE", "INSUFFICIENT_EVIDENCE")[
        i % 4
    ]
    selected = {
        "SUPPORTED": [row["support"]],
        "UNSUPPORTED": [row["contradict"]],
        "MIXED_EVIDENCE": [row["support"], row["contradict"]],
        "INSUFFICIENT_EVIDENCE": [row["neutral"]],
    }[expected]
    sources = [
        {
            "url": f"https://source{j}.example.gov/{group}",
            "passage": p,
            "published_at": None,
        }
        for j, p in enumerate(selected)
    ]
    # Related noise repeated on one page tests independence without changing gold.
    sources += [
        {
            "url": f"https://noise.example.org/{group}",
            "passage": row["neutral"],
            "published_at": None,
        }
        for _ in range(5)
    ]
    if row["tag"] in ("compound", "multi_source") and expected == "SUPPORTED":
        sources = [
            {
                "url": f"https://source{j}.example.gov/{group}",
                "passage": p.strip() + ".",
                "published_at": None,
            }
            for j, p in enumerate(row["support"].split(". "))
        ]
    verdicts.append(
        dict(meta, id=group, claim=row["claim"], sources=sources, expected=expected)
    )
for name, data in [("nli", nli), ("retrieval", retrieval), ("verdicts", verdicts)]:
    (ROOT / f"data/{name}.json").write_text(json.dumps(data, indent=2) + "\n")
manifest = {
    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
    for p in (ROOT / "data").iterdir()
    if p.name != "manifest.json"
}
(ROOT / "data/manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print({"nli": len(nli), "retrieval": len(retrieval), "verdicts": len(verdicts)})
