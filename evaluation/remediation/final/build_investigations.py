"""Remediation pass 5, part 17: assemble the NEW 150-case confirmation
investigation set (40 easy / 50 medium / 60 hard) from freshly authored
facts, freshly authored hard scenarios, and a fresh, previously-unused
SciFact-dev pull -- disjoint from Pass 2, the old final corpus, AND the
Group 4 Hyper holdout. Never tuned on; run once (part 16/17)."""

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
        url=f"https://remediation-source-{i}.org/document",
        passage=passage,
        published_at=None,
        title=title,
    )


def build_facts_tier():
    facts = json.loads((DATA / "facts.json").read_text())
    assert len(facts) >= 90
    facts.sort(key=lambda r: digest(r["fact"]))
    easy_facts, medium_facts = facts[:40], facts[40:90]

    rng = random.Random(20260915)
    easy_labels = ["SUPPORTED"] * 20 + ["UNSUPPORTED"] * 20
    medium_labels = (
        ["SUPPORTED"] * 18 + ["UNSUPPORTED"] * 17 + ["INSUFFICIENT_EVIDENCE"] * 15
    )
    rng.shuffle(easy_labels)
    rng.shuffle(medium_labels)

    rows = []
    for i, (fact, expected) in enumerate(zip(easy_facts, easy_labels, strict=True)):
        claim = fact["alternative"] if expected == "UNSUPPORTED" else fact["fact"]
        sources = [source(f"easy-{i}", fact["fact"])]
        rows.append(
            dict(
                id=f"remediation-fact-{i:03}",
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
                        "Site footer: privacy policy, cookie settings, "
                        "social media links and newsletter signup. " * 6,
                    )
                )
        rows.append(
            dict(
                id=f"remediation-fact-{40 + i:03}",
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
                id=f"remediation-hard-{i:03}",
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
    limits = {"SUPPORTED": 12, "UNSUPPORTED": 12, "INSUFFICIENT_EVIDENCE": 11}
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
                id=f"remediation-scifact-{row['id']}",
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
    old_scifact_doc_ids = set()
    old_scifact_claim_ids = set()
    # Exclude every SciFact doc/claim ID already consumed by the old final
    # corpus AND the Group 4 Hyper holdout, not just the former.
    for path, prefix in [
        (
            Path(__file__).resolve().parents[2] / "final/data/verdicts.json",
            "final-scifact-",
        ),
        (
            Path(__file__).resolve().parents[2]
            / "hyper/final/data/investigations.json",
            "hyper-scifact-",
        ),
    ]:
        for r in json.loads(path.read_text()):
            if r["origin"] == "SciFact-dev":
                old_scifact_claim_ids.add(int(r["id"].removeprefix(prefix)))
                for s in r["sources"]:
                    if "corpus_doc_id" in s:
                        old_scifact_doc_ids.add(s["corpus_doc_id"])

    easy_medium = build_facts_tier()
    hard_authored = build_hard_authored()
    hard_scifact = build_scifact_fresh(
        old_scifact_doc_ids, old_scifact_claim_ids, len(hard_authored)
    )

    combined = easy_medium + hard_authored + hard_scifact
    assert sum(1 for r in combined if r["difficulty"] == "easy") == 40
    assert sum(1 for r in combined if r["difficulty"] == "medium") == 50
    assert sum(1 for r in combined if r["difficulty"] == "hard") == 60
    assert len(combined) == 150
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
