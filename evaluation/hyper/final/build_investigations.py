"""Group 4, phase 3: assemble the new 250-case controlled investigation set
(60 easy / 90 medium / 100 hard) from freshly authored facts, freshly
authored hard scenarios, and a fresh, previously-unused SciFact-dev pull.
"""

import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def source(i, passage, title="Controlled source"):
    return dict(
        url=f"https://hyper-source-{i}.org/document",
        passage=passage,
        published_at=None,
        title=title,
    )


def build_facts_tier():
    facts = json.loads((DATA / "facts.json").read_text())
    assert len(facts) == 160
    facts.sort(key=lambda r: digest(r["fact"]))
    easy_facts, medium_facts = facts[:60], facts[60:150]

    rng = random.Random(20260914)
    easy_labels = ["SUPPORTED"] * 30 + ["UNSUPPORTED"] * 30
    medium_labels = (
        ["SUPPORTED"] * 35 + ["UNSUPPORTED"] * 30 + ["INSUFFICIENT_EVIDENCE"] * 25
    )
    rng.shuffle(easy_labels)
    rng.shuffle(medium_labels)

    rows = []
    for i, (fact, expected) in enumerate(zip(easy_facts, easy_labels, strict=True)):
        claim = fact["alternative"] if expected == "UNSUPPORTED" else fact["fact"]
        sources = [source(f"easy-{i}", fact["fact"])]
        rows.append(
            dict(
                id=f"hyper-fact-{i:03}",
                split="test",
                difficulty="easy",
                domain=fact["domain"],
                tag="direct-factual",
                claim=claim,
                sources=sources,
                expected=expected,
                origin="authored-controlled",
                gold_scope=(
                    "Supplied evidence only; authored summaries, not source quotations."
                ),
            )
        )
    for i, (fact, expected) in enumerate(zip(medium_facts, medium_labels, strict=True)):
        claim = fact["alternative"] if expected == "UNSUPPORTED" else fact["fact"]
        if expected == "INSUFFICIENT_EVIDENCE":
            sources = []
        else:
            sources = [source(f"med-{i}", fact["fact"])]
            if i % 3 == 0:
                sources.append(
                    source(
                        f"med-{i}-noise",
                        "Navigation: contact information, archive index "
                        "and terms of use. " * 6,
                    )
                )
        rows.append(
            dict(
                id=f"hyper-fact-{60 + i:03}",
                split="test",
                difficulty="medium",
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
    return rows


def build_hard_authored():
    hard = json.loads((DATA / "hard.json").read_text())
    rows = []
    for i, row in enumerate(hard):
        rows.append(
            dict(
                id=f"hyper-hard-{i:03}",
                split="test",
                difficulty="hard",
                domain=row["domain"],
                tag=row["tag"],
                claim=row["claim"],
                sources=[
                    source(f"hard-{i}-{j}", s["passage"])
                    for j, s in enumerate(row["sources"])
                ],
                expected=row["expected"],
                origin="authored-controlled",
                gold_scope=(
                    "Supplied evidence only; hypothetical conflicts are "
                    "controlled scenarios."
                ),
            )
        )
    return rows


def build_scifact_fresh(exclude_doc_ids, exclude_claim_ids, start_index):
    corpus = {
        r["doc_id"]: r
        for line in (
            Path(__file__).resolve().parents[2] / "final/data/scifact-corpus.jsonl"
        )
        .read_text()
        .splitlines()
        if (r := json.loads(line))
    }
    claims = [
        json.loads(line)
        for line in (
            Path(__file__).resolve().parents[2] / "final/data/scifact-claims-dev.jsonl"
        )
        .read_text()
        .splitlines()
    ]
    seen_docs = set(exclude_doc_ids)
    counts = {"SUPPORTED": 0, "UNSUPPORTED": 0, "INSUFFICIENT_EVIDENCE": 0}
    limits = {"SUPPORTED": 16, "UNSUPPORTED": 16, "INSUFFICIENT_EVIDENCE": 12}
    rows = []
    for row in sorted(claims, key=lambda r: digest(r["claim"])):
        if row["id"] in exclude_claim_ids:
            continue
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
                id=f"hyper-scifact-{row['id']}",
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
    return rows


def main():
    old_verdicts = json.loads(
        (Path(__file__).resolve().parents[2] / "final/data/verdicts.json").read_text()
    )
    old_scifact_doc_ids = set()
    old_scifact_claim_ids = set()
    for r in old_verdicts:
        if r["origin"] == "SciFact-dev":
            old_scifact_claim_ids.add(int(r["id"].removeprefix("final-scifact-")))
            for s in r["sources"]:
                if "corpus_doc_id" in s:
                    old_scifact_doc_ids.add(s["corpus_doc_id"])

    easy_medium = build_facts_tier()
    hard_authored = build_hard_authored()
    hard_scifact = build_scifact_fresh(
        old_scifact_doc_ids, old_scifact_claim_ids, len(hard_authored)
    )

    combined = easy_medium + hard_authored + hard_scifact
    assert sum(1 for r in combined if r["difficulty"] == "easy") == 60
    assert sum(1 for r in combined if r["difficulty"] == "medium") == 90
    assert sum(1 for r in combined if r["difficulty"] == "hard") == 100
    assert len(combined) == 250
    assert len({r["claim"].casefold() for r in combined}) == len(combined), (
        "duplicate claim text"
    )

    (DATA / "investigations.json").write_text(json.dumps(combined, indent=2) + "\n")
    from collections import Counter

    print("Total:", len(combined))
    print("By difficulty:", dict(Counter(r["difficulty"] for r in combined)))
    print("By expected:", dict(Counter(r["expected"] for r in combined)))
    print("By origin:", dict(Counter(r["origin"] for r in combined)))
    print(
        "SHA256:",
        hashlib.sha256((DATA / "investigations.json").read_bytes()).hexdigest(),
    )


if __name__ == "__main__":
    main()
