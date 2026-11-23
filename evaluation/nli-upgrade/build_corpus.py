"""NLI upgrade pass, Phases 1-4, 8, 11: build the training/validation NLI
corpus. Documented provenance, explicit label mapping, deliberate mix
(not a blind concatenation), emphasis on the diagnosed failure modes
(scientific/dense text, hard neutrals, hard contradictions).

Sources:
  - SciFact train split (809 claims, freshly downloaded from the official
    release -- NEVER touched by any prior pass, which only ever used the
    300-claim dev split). Real scientific SUPPORT/CONTRADICT/NEI claims.
  - MNLI (general-domain diversity, sampled, not the full 392k).
  - FEVER-NLI (`pietrolesci/nli_fever` -- closer to Claim Check's actual
    fact-verification domain than generic MNLI; sampled).
  - Hand-authored hard negatives (Phase 2: same topic, different
    proposition -- high lexical overlap, correct label is NEUTRAL).
  - Hand-authored hard contradictions (Phase 3: numeric, temporal,
    negation, relation-reversal, implicit/scientific contradiction).

Explicitly excludes: the Group 4 Hyper holdout and the remediation
confirmation holdout (diagnostic/historical-comparison only, per Rule 1 --
never a training source), and every prior pass's already-built NLI/
investigation corpora (to avoid duplicate exact text, not because they're
off-limits for training, simply to keep this corpus additive).
"""

import hashlib
import json
import random
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROOT = Path(__file__).resolve().parent
RNG = random.Random(20260916)

LABELS = {"support": "support", "neutral": "neutral", "contradict": "contradict"}


def norm(text):
    return " ".join(text.casefold().split())


def digest(text):
    return hashlib.sha256(norm(text).encode()).hexdigest()


def load_forbidden_texts():
    """Every claim/passage text from the two independent holdouts --
    never used for training or validation (Rule 1)."""
    forbidden = set()
    for root in [
        REPO / "evaluation/hyper/final",
        REPO / "evaluation/remediation/final",
    ]:
        nli_path = root / "data/nli.json"
        if nli_path.exists():
            for r in json.loads(nli_path.read_text()):
                for k in ("claim", "passage"):
                    if r.get(k):
                        forbidden.add(digest(r[k]))
        inv_path = root / "data/investigations.json"
        if inv_path.exists():
            for r in json.loads(inv_path.read_text()):
                if r.get("claim"):
                    forbidden.add(digest(r["claim"]))
                for s in r.get("sources") or []:
                    if s.get("passage"):
                        forbidden.add(digest(s["passage"]))
    return forbidden


def scifact_pairs(forbidden):
    claims = [
        json.loads(line)
        for line in (ROOT / "data/scifact-claims-train.jsonl").read_text().splitlines()
    ]
    corpus = {
        r["doc_id"]: r
        for line in (REPO / "evaluation/final/data/scifact-corpus.jsonl")
        .read_text()
        .splitlines()
        if (r := json.loads(line))
    }
    rows = []
    nei_claims = []
    for c in claims:
        all_labels = {e["label"] for entries in c["evidence"].values() for e in entries}
        cited = c.get("cited_doc_ids") or []
        if not all_labels:
            nei_claims.append(c)
            continue
        label = (
            "support"
            if all_labels == {"SUPPORT"}
            else "contradict"
            if all_labels == {"CONTRADICT"}
            else None
        )
        if label is None:
            continue  # mixed-evidence claim, not a clean 3-way NLI label
        docs = set(int(x) for x in c["evidence"]) | set(cited)
        for doc in docs:
            if doc not in corpus:
                continue
            passage = " ".join(corpus[doc]["abstract"])
            if digest(c["claim"]) in forbidden or digest(passage) in forbidden:
                continue
            rows.append(
                dict(
                    id=f"scifact-train-{c['id']}-{doc}",
                    claim=c["claim"],
                    passage=passage,
                    label=label,
                    domain="science",
                    tag="scifact-train",
                    origin="SciFact-train",
                )
            )
    # NEI (no-evidence) claims -> neutral pairs against the doc they cited
    # (annotators considered it but found it insufficient) -- a genuinely
    # hard, on-topic neutral, not a random unrelated pairing.
    for c in nei_claims:
        cited = c.get("cited_doc_ids") or []
        if not cited or cited[0] not in corpus:
            continue
        passage = " ".join(corpus[cited[0]]["abstract"])
        if digest(c["claim"]) in forbidden or digest(passage) in forbidden:
            continue
        rows.append(
            dict(
                id=f"scifact-train-nei-{c['id']}",
                claim=c["claim"],
                passage=passage,
                label="neutral",
                domain="science",
                tag="scifact-train-nei",
                origin="SciFact-train",
            )
        )
    return rows


def mnli_pairs(forbidden, per_label=130):
    from datasets import load_dataset

    ds = load_dataset("nyu-mll/multi_nli", split="train")
    mapped = {0: "support", 1: "neutral", 2: "contradict"}
    counts = {"support": 0, "neutral": 0, "contradict": 0}
    rows = []
    indices = list(range(len(ds)))
    RNG.shuffle(indices)
    for i in indices:
        if all(c >= per_label for c in counts.values()):
            break
        row = ds[i]
        label = mapped[row["label"]]
        if counts[label] >= per_label:
            continue
        if (
            digest(row["premise"]) in forbidden
            or digest(row["hypothesis"]) in forbidden
        ):
            continue
        rows.append(
            dict(
                id=f"mnli-{row['pairID']}",
                claim=row["hypothesis"],
                passage=row["premise"],
                label=label,
                domain=row.get("genre", "general"),
                tag="mnli",
                origin="MNLI",
            )
        )
        counts[label] += 1
    return rows


def fever_pairs(forbidden, per_label=170):
    from datasets import load_dataset

    ds = load_dataset("pietrolesci/nli_fever", split="train")
    # NOTE (phase 11 label-mapping sanity): in THIS dataset the field named
    # "premise" actually holds the short FEVER claim, and "hypothesis"
    # holds the long extracted-evidence context -- the reverse of what the
    # field names suggest. Verified by direct inspection before use. Mapped
    # here by CONTENT (claim -> our claim slot, evidence -> our passage
    # slot), not by field name.
    mapped = {0: "support", 1: "neutral", 2: "contradict"}
    counts = {"support": 0, "neutral": 0, "contradict": 0}
    rows = []
    indices = list(range(len(ds)))
    RNG.shuffle(indices)
    for i in indices:
        if all(c >= per_label for c in counts.values()):
            break
        row = ds[i]
        label = mapped[row["label"]]
        if counts[label] >= per_label:
            continue
        claim_text, evidence_text = row["premise"], row["hypothesis"]
        if digest(claim_text) in forbidden or digest(evidence_text) in forbidden:
            continue
        rows.append(
            dict(
                id=f"fever-{row['cid']}-{row['fid']}",
                claim=claim_text,
                passage=evidence_text,
                label=label,
                domain="general-factual",
                tag="fever-nli",
                origin="FEVER-NLI",
            )
        )
        counts[label] += 1
    return rows


def authored_pairs(name, tag):
    triples = json.loads((ROOT / "data" / name).read_text())
    rows = []
    for t in triples:
        rows.append(
            dict(
                id=t["id"] + "-support",
                claim=t["claim"],
                passage=t["passage_support"],
                label="support",
                domain=t["domain"],
                tag=tag,
                origin="authored",
            )
        )
        rows.append(
            dict(
                id=t["id"] + "-contradict",
                claim=t["claim"],
                passage=t["passage_contradict"],
                label="contradict",
                domain=t["domain"],
                tag=tag,
                origin="authored",
            )
        )
        rows.append(
            dict(
                id=t["id"] + "-neutral",
                claim=t["claim"],
                passage=t["passage_neutral"],
                label="neutral",
                domain=t["domain"],
                tag=tag,
                origin="authored",
            )
        )
    return rows


def main():
    forbidden = load_forbidden_texts()
    print(f"Forbidden texts loaded (both independent holdouts): {len(forbidden)}")

    scifact = scifact_pairs(forbidden)
    print(f"SciFact-train pairs: {len(scifact)}")

    mnli = mnli_pairs(forbidden)
    print(f"MNLI sampled pairs: {len(mnli)}")

    fever = fever_pairs(forbidden)
    print(f"FEVER-NLI sampled pairs: {len(fever)}")

    hard_negatives = authored_pairs("hard-negatives.json", "hard-negative-authored")
    print(f"Hard-negative authored pairs: {len(hard_negatives)}")

    hard_contradictions = authored_pairs(
        "hard-contradictions.json", "hard-contradiction-authored"
    )
    print(f"Hard-contradiction authored pairs: {len(hard_contradictions)}")

    combined = scifact + mnli + fever + hard_negatives + hard_contradictions

    # Internal dedup (claim+passage exact match).
    seen = set()
    deduped = []
    for r in combined:
        key = (digest(r["claim"]), digest(r["passage"]))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    n_removed = len(combined) - len(deduped)
    print(f"\nTotal after internal dedup: {len(deduped)} (removed {n_removed})")

    from collections import Counter

    print("By label:", dict(Counter(r["label"] for r in deduped)))
    print("By origin:", dict(Counter(r["origin"] for r in deduped)))

    # Split: 80% train / 20% validation, stratified by (origin, label) so
    # every source and label is represented in both splits.
    by_group = {}
    for r in deduped:
        by_group.setdefault((r["origin"], r["label"]), []).append(r)
    train, validation = [], []
    for rows in by_group.values():
        rows = sorted(rows, key=lambda r: digest(r["id"]))
        cut = max(1, int(len(rows) * 0.8)) if len(rows) > 1 else len(rows)
        train += rows[:cut]
        validation += rows[cut:]

    print(f"\nTrain: {len(train)}  Validation: {len(validation)}")
    print("Train by label:", dict(Counter(r["label"] for r in train)))
    print("Validation by label:", dict(Counter(r["label"] for r in validation)))

    (ROOT / "data/train.json").write_text(json.dumps(train, indent=2) + "\n")
    (ROOT / "data/validation.json").write_text(json.dumps(validation, indent=2) + "\n")
    print("\nWrote data/train.json and data/validation.json")


if __name__ == "__main__":
    main()
