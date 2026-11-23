"""Remediation pass 5, Part 2: build a NEW, multi-fold contradiction
calibration corpus. Disjoint from every prior corpus in the repo, including
the Group 4 Hyper holdout (which is diagnostic-only from here on, never a
tuning target -- see Part 16 of the remediation instructions).

Mines fresh pairs from the same 2400-pair ANLI source pool used by earlier
passes (1320 of 2400 already consumed: 600 by pass2, 720 by the Hyper
final holdout), leaving ~1080 unused, plus the 84 hand-authored pairs in
data/contradiction-authored.json stress-testing 14 explicit categories.
Assigns 3 balanced folds for cross-validation (Part 2: "Use at least THREE
validation folds. Do not select one threshold from one split.").
"""

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVAL_ROOT = ROOT.parent


def digest(text):
    return hashlib.sha256(" ".join(text.casefold().split()).encode()).hexdigest()


def collect_seen():
    """Every claim/passage/premise/hypothesis ever consumed by a prior
    corpus in this repo -- pass2, final, and the Hyper final holdout --
    so this new corpus is guaranteed disjoint from all of them."""
    seen = set()
    old_pass2 = EVAL_ROOT / "pass2/data/anli-source.json"
    if old_pass2.exists():
        for r in json.loads(old_pass2.read_text()):
            seen.add(digest(r["premise"]))
    for path in EVAL_ROOT.glob("**/nli.json"):
        if ROOT in path.parents or path.parent == ROOT:
            continue
        rows = json.loads(path.read_text())
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict):
                for k in ("passage", "claim"):
                    if row.get(k):
                        seen.add(digest(row[k]))
    for pattern in [
        "**/retrieval-probes.json",
        "**/compound-probes.json",
        "**/verdicts.json",
        "**/missed-contradictions-pairs.json",
        "**/investigations.json",
    ]:
        for path in EVAL_ROOT.glob(pattern):
            if ROOT in path.parents or path.parent == ROOT:
                continue
            rows = json.loads(path.read_text())
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                for key in ("claim", "passage"):
                    if row.get(key):
                        seen.add(digest(row[key]))
                for src in row.get("sources") or []:
                    if isinstance(src, dict) and src.get("passage"):
                        seen.add(digest(src["passage"]))
                for atom in row.get("atoms") or []:
                    if atom.get("claim"):
                        seen.add(digest(atom["claim"]))
                    for src in atom.get("sources") or []:
                        if src.get("passage"):
                            seen.add(digest(src["passage"]))
                for q_rows in (row.get("queries") or {}).values():
                    for r in q_rows:
                        if r.get("passage"):
                            seen.add(digest(r["passage"]))
    return seen


def mine(seen, per_label_target):
    candidates = json.loads((EVAL_ROOT / "final/data/anli-source.json").read_text())
    counts = Counter()
    result = []
    for row in sorted(candidates, key=lambda r: digest(r["premise"] + r["hypothesis"])):
        label = {0: "support", 1: "neutral", 2: "contradict"}[row["label"]]
        if (
            counts[label] == per_label_target
            or digest(row["premise"]) in seen
            or digest(row["hypothesis"]) in seen
        ):
            continue
        seen.update([digest(row["premise"]), digest(row["hypothesis"])])
        result.append(
            dict(
                id="rem-anli-" + row["uid"],
                claim=row["hypothesis"],
                passage=row["premise"],
                label=label,
                category="ANLI-unannotated",
                tag=row["source_split"],
                origin="ANLI",
            )
        )
        counts[label] += 1
    return result, counts


def assign_folds(rows, n_folds=3):
    """Deterministic, label-balanced fold assignment: sort within each label
    by hash and round-robin across folds, so each fold gets a near-identical
    label distribution -- required for comparing precision/recall across
    folds without a label-imbalance confound."""
    by_label = {}
    for r in rows:
        by_label.setdefault(r["label"], []).append(r)
    for group in by_label.values():
        group.sort(key=lambda r: digest(r["id"]))
        for i, r in enumerate(group):
            r["fold"] = i % n_folds
    return rows


def main():
    seen = collect_seen()
    authored = json.loads((ROOT / "data/contradiction-authored.json").read_text())
    for r in authored:
        r["origin"] = "authored"
        r["tag"] = "remediation-authored"
        seen.add(digest(r["claim"]))
        seen.add(digest(r["passage"]))

    # 200/label mined (600 total) -- comfortably above the 600-pair minimum
    # once combined with the 84 authored pairs (684 total).
    mined, counts = mine(seen, per_label_target=200)
    if any(c < 200 for c in counts.values()):
        raise SystemExit(f"ANLI pool exhausted before reaching target: {dict(counts)}")

    combined = mined + authored
    combined = assign_folds(combined, n_folds=3)

    out = ROOT / "data/contradiction-corpus.json"
    out.write_text(json.dumps(combined, indent=2) + "\n")
    print("Mined counts:", dict(counts))
    print("Authored:", len(authored))
    print("Total:", len(combined))
    print("By label:", dict(Counter(r["label"] for r in combined)))
    print("By fold:", dict(Counter(r["fold"] for r in combined)))
    print(
        "By fold x label:",
        dict(Counter((r["fold"], r["label"]) for r in combined)),
    )
    print("SHA256:", hashlib.sha256(out.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
