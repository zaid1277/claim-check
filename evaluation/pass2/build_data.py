"""Freeze independent pair and verdict corpora before inference."""

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "data"


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def read_tsv(name):
    return list(csv.DictReader((ROOT / name).open(), delimiter="\t"))


def write(name, data):
    (ROOT / name).write_text(json.dumps(data, indent=2) + "\n")


nli = []
core = read_tsv("core.tsv")
for i, r in enumerate(core):
    split = ["development", "validation", "test"][i % 3]
    for label in ["support", "contradict", "neutral"]:
        nli.append(
            dict(
                id=f"core-{i:02}-{label}",
                group=f"core-{i:02}",
                split=split,
                domain=r["domain"],
                tag=r["tag"],
                claim=r["claim"],
                passage=r[label],
                label=label,
                published_at="2026-09-13"
                if r["tag"] == "current" and label != "neutral"
                else None,
                origin="authored",
            )
        )
seen = set()
selected = Counter()
buckets = defaultdict(list)
for r in sorted(
    json.loads((ROOT / "anli-source.json").read_text()),
    key=lambda r: digest(r["premise"] + r["hypothesis"]),
):
    key = digest(r["premise"].strip().casefold())
    if key in seen or selected[r["label"]] >= 100:
        continue
    seen.add(key)
    selected[r["label"]] += 1
    buckets[r["label"]].append(r)
assert selected == {0: 100, 1: 100, 2: 100}, selected
for label, rows in buckets.items():
    for i, r in enumerate(rows):
        split = "development" if i < 50 else "validation" if i < 75 else "test"
        nli.append(
            dict(
                id="anli-" + r["uid"],
                group=digest(r["premise"].strip().casefold()),
                split=split,
                domain="ANLI-unannotated",
                tag=r["source_split"],
                claim=r["hypothesis"],
                passage=r["premise"],
                label={0: "support", 1: "neutral", 2: "contradict"}[label],
                published_at=None,
                origin="ANLI",
            )
        )
write("nli.json", nli)
rows = read_tsv("verdicts.tsv")
assert len(rows) == 100, len(rows)
assert Counter(r["difficulty"] for r in rows) == {"easy": 35, "medium": 40, "hard": 25}
strata = defaultdict(list)
for i, r in enumerate(rows):
    strata[(r["difficulty"], r["expected"])].append(i)
splits = {}
for indices in strata.values():
    indices.sort(key=lambda i: digest(rows[i]["claim"]))
    n = len(indices)
    test = max(1, round(n * 0.3))
    val = max(1, round(n * 0.2))
    for j, i in enumerate(indices):
        splits[i] = (
            "test" if j < test else "validation" if j < test + val else "development"
        )
verdicts = []
retrieval = []
for i, r in enumerate(rows):
    sources = []
    relevant = []
    for j, p in enumerate(r["evidence"].split("||")):
        date = (
            "2001-01-01"
            if p.startswith("[old]")
            else "2026-09-13"
            if p.startswith("[recent]")
            else None
        )
        p = p.removeprefix("[old] ").removeprefix("[recent] ")
        sources.append(
            dict(
                url=f"https://record{j}.example.gov/case-{i}",
                passage=p,
                published_at=date,
            )
        )
        if r["expected"] != "INSUFFICIENT_EVIDENCE":
            relevant.append(j)
    distractors = [r["distractor"].removeprefix("[old] ").removeprefix("[copy] ")]
    # Fixed nuisance documents supplement the same-topic distractor.
    distractors += [
        rows[(i + 7 * j) % 100]["distractor"]
        .removeprefix("[old] ")
        .removeprefix("[copy] ")
        for j in range(1, 10)
    ]
    for j, p in enumerate(distractors):
        sources.append(
            dict(
                url=f"https://context{j}.example.org/case-{i}",
                passage=p,
                published_at="2001-01-01"
                if j == 0 and r["distractor"].startswith("[old]")
                else None,
            )
        )
    meta = dict(
        id=f"e2e-{i:03}",
        group=f"e2e-{i:03}",
        split=splits[i],
        difficulty=r["difficulty"],
        domain=r["domain"],
        claim=r["claim"],
    )
    verdicts.append(dict(meta, expected=r["expected"], sources=sources))
    retrieval.append(
        dict(meta, passages=[s["passage"] for s in sources], relevant=relevant)
    )
assert not {r["claim"] for r in nli} & {r["claim"] for r in verdicts}
write("verdicts.json", verdicts)
write("retrieval.json", retrieval)
write(
    "manifest.json",
    {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in ROOT.iterdir()
        if p.name != "manifest.json"
    },
)
print(
    {
        name: dict(Counter(r["split"] for r in data))
        for name, data in [("nli", nli), ("verdicts", verdicts)]
    }
)
