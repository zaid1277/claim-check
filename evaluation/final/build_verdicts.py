"""Build controlled cases before inference; evidence fixtures are not web citations."""

import csv
import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"


def read_tsv(name):
    with (DATA / name).open() as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def source(i, passage):
    return dict(
        url=f"https://source-{i}.org/document", passage=passage, published_at=None
    )


def write(name, rows):
    (DATA / name).write_text(json.dumps(rows, indent=2) + "\n")


facts = read_tsv("facts.tsv")
assert len(facts) == 100
# Hash order avoids making difficulty a proxy for domain or file position.
facts.sort(key=lambda r: hashlib.sha256(r["fact"].encode()).hexdigest())
easy = ["SUPPORTED"] * 20 + ["UNSUPPORTED"] * 20
medium = ["SUPPORTED"] * 25 + ["UNSUPPORTED"] * 20 + ["INSUFFICIENT_EVIDENCE"] * 15
rng = random.Random(20260913)
rng.shuffle(easy)
rng.shuffle(medium)
assignments = easy + medium
rows = []
for i, (fact, expected) in enumerate(zip(facts, assignments, strict=True)):
    claim = fact["alternative"] if expected == "UNSUPPORTED" else fact["fact"]
    evidence = fact["fact"]
    # Empty search is an explicit retrieval-failure control, not an NLI neutral pair.
    sources = [] if expected == "INSUFFICIENT_EVIDENCE" else [source(0, evidence)]
    if i >= 40 and sources:
        sources += [
            source(
                1,
                "Navigation: contact information, archive index and terms of use. " * 8,
            )
        ]
    rows.append(
        dict(
            id=f"final-fact-{i:03}",
            split="test",
            difficulty="easy" if i < 40 else "medium",
            domain=fact["domain"],
            tag="empty-retrieval" if not sources else "direct-factual",
            claim=claim,
            sources=sources,
            expected=expected,
            origin="authored-controlled",
            gold_scope=(
                "Supplied evidence only; authored summaries, not source quotations."
            ),
        )
    )
for i, row in enumerate(read_tsv("hard.tsv")):
    rows.append(
        dict(
            id=f"final-hard-{i:03}",
            split="test",
            difficulty="hard",
            domain=row["domain"],
            tag=row["tag"],
            claim=row["claim"],
            expected=row["expected"],
            sources=[source(j, row[f"passage{j + 1}"]) for j in range(2)],
            origin="authored-controlled",
            gold_scope=(
                "Supplied evidence only; hypothetical conflicts are "
                "controlled scenarios."
            ),
        )
    )
corpus = {
    r["doc_id"]: r
    for line in (DATA / "scifact-corpus.jsonl").read_text().splitlines()
    if (r := json.loads(line))
}
claims = [
    json.loads(line)
    for line in (DATA / "scifact-claims-dev.jsonl").read_text().splitlines()
]
seen_docs = set()
counts = {"SUPPORTED": 0, "UNSUPPORTED": 0, "INSUFFICIENT_EVIDENCE": 0}
limits = {"SUPPORTED": 20, "UNSUPPORTED": 20, "INSUFFICIENT_EVIDENCE": 10}
for row in sorted(
    claims, key=lambda r: hashlib.sha256(r["claim"].encode()).hexdigest()
):
    labels = {e["label"] for entries in row["evidence"].values() for e in entries}
    expected = (
        "INSUFFICIENT_EVIDENCE"
        if not labels
        else "SUPPORTED"
        if labels == {"SUPPORT"}
        else "UNSUPPORTED"
        if labels == {"CONTRADICT"}
        else None
    )
    docs = set(row["cited_doc_ids"]) | {int(x) for x in row["evidence"]}
    if expected is None or counts[expected] == limits[expected] or docs & seen_docs:
        continue
    seen_docs.update(docs)
    counts[expected] += 1
    sources = [
        dict(
            url=f"https://scifact-corpus.org/abstract/{doc}",
            passage=" ".join(corpus[doc]["abstract"]),
            title=corpus[doc]["title"],
            published_at=None,
            corpus_doc_id=doc,
        )
        for doc in sorted(docs)
    ]
    rows.append(
        dict(
            id=f"final-scifact-{row['id']}",
            split="test",
            difficulty="hard",
            domain="health/science",
            tag="expert-scientific",
            claim=row["claim"],
            sources=sources,
            expected=expected,
            origin="SciFact-dev",
            gold_scope="Original human annotation over cited abstracts.",
            original_annotations=row["evidence"],
        )
    )
assert counts == limits, counts
assert len({r["claim"].casefold() for r in rows}) == len(rows)
nli = json.loads((DATA / "nli.json").read_text())
assert not (
    {r["claim"].casefold() for r in rows} & {r["claim"].casefold() for r in nli}
)
write("verdicts.json", rows)
write(
    "verdict-manifest.json",
    {
        "count": len(rows),
        "scifact_counts": counts,
        "sha256": hashlib.sha256((DATA / "verdicts.json").read_bytes()).hexdigest(),
        "methodology": (
            "Controlled evidence. Not measured live truth accuracy. "
            "25 authored hard scenarios include hypothetical "
            "conflict/absence probes."
        ),
    },
)
print(
    "Frozen", len(rows), "distinct held-out investigations; no predictions inspected."
)
