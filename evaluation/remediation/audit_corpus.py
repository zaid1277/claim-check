"""Remediation pass 5: leakage audit for the new contradiction corpus
against every prior corpus in the repo, including the Group 4 Hyper
holdout (diagnostic-only, must never be a tuning target -- confirming here
that this new corpus doesn't silently duplicate it is part of guaranteeing
that)."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVAL_ROOT = ROOT.parent


def norm(text):
    return " ".join(text.casefold().split())


def digest(text):
    return hashlib.sha256(norm(text).encode()).hexdigest()


def words(text):
    return set(norm(text).split())


def load_prior():
    # Note: anli-source.json (the raw 2400-pair pool) is deliberately NOT
    # scanned here, same reasoning as evaluation/hyper/final/
    # build_and_audit_nli.py: build_corpus.py's own `seen` set already
    # excludes every premise/hypothesis consumed by any prior project from
    # this pool at mining time, so every mined pair here is guaranteed
    # disjoint from anything the pool was previously used for. Scanning the
    # pool itself would flag every mined row as "overlapping" with the very
    # pool it was legitimately drawn from -- not leakage.
    items = []
    for pattern in [
        "**/nli.json",
        "**/verdicts.json",
        "**/retrieval-probes.json",
        "**/compound-probes.json",
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
                for key in ("claim", "passage", "premise", "hypothesis"):
                    if row.get(key):
                        items.append((str(path), key, row[key]))
                for src in row.get("sources") or []:
                    if isinstance(src, dict) and src.get("passage"):
                        items.append((str(path), "source-passage", src["passage"]))
    return items


def main():
    new_rows = json.loads((ROOT / "data/contradiction-corpus.json").read_text())
    prior = load_prior()
    prior_hash_index = {}
    for path, field, text in prior:
        prior_hash_index.setdefault(digest(text), []).append((path, field))

    exact_overlaps = []
    for r in new_rows:
        for k in ("claim", "passage"):
            d = digest(r[k])
            if d in prior_hash_index:
                exact_overlaps.append(
                    {"new_id": r["id"], "field": k, "matched_in": prior_hash_index[d]}
                )

    prior_claim_texts = [(p, t) for p, f, t in prior if f in ("claim", "hypothesis")]
    near_dupes = []
    for r in new_rows:
        rw = words(r["claim"])
        if not rw:
            continue
        for path, text in prior_claim_texts:
            tw = words(text)
            if not tw:
                continue
            jaccard = len(rw & tw) / len(rw | tw)
            if jaccard >= 0.9 and digest(r["claim"]) != digest(text):
                near_dupes.append(
                    {
                        "new_id": r["id"],
                        "matched_in": path,
                        "jaccard": round(jaccard, 3),
                    }
                )

    seen = {}
    internal_dupes = []
    for r in new_rows:
        d = digest(r["claim"])
        if d in seen:
            internal_dupes.append((r["id"], seen[d]))
        seen[d] = r["id"]

    audit = {
        "new_case_count": len(new_rows),
        "prior_items_scanned": len(prior),
        "exact_overlaps": exact_overlaps,
        "near_duplicate_claims": near_dupes,
        "internal_duplicates": internal_dupes,
    }
    (ROOT / "data/contradiction-corpus-leakage-audit.json").write_text(
        json.dumps(audit, indent=2)
    )
    print("prior_items_scanned:", len(prior))
    print("exact_overlaps:", len(exact_overlaps))
    print("near_duplicate_claims (>=90% jaccard):", len(near_dupes))
    print("internal_duplicates:", len(internal_dupes))
    for n in near_dupes[:20]:
        print(" ", n)
    for e in exact_overlaps[:20]:
        print(" EXACT:", e)
    if exact_overlaps or internal_dupes:
        raise SystemExit("Leakage detected -- resolve before running any evaluation.")


if __name__ == "__main__":
    main()
