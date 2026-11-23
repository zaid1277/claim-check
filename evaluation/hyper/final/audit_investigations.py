"""Group 4, phase 4: leakage audit for the new 250-case investigation set
against every prior corpus in the repo (Pass 2, old final corpus, Group 1-3
probes, NLI sets)."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVAL_ROOT = ROOT.parents[1]


def norm(text):
    return " ".join(text.casefold().split())


def digest(text):
    return hashlib.sha256(norm(text).encode()).hexdigest()


def words(text):
    return set(norm(text).split())


def load_prior_claims_and_passages():
    items = []  # (source_path, field, text)
    patterns = [
        "**/verdicts.json",
        "**/nli.json",
        "**/retrieval-probes.json",
        "**/compound-probes.json",
        "**/missed-contradictions-pairs.json",
    ]
    for pattern in patterns:
        for path in EVAL_ROOT.glob(pattern):
            if ROOT in path.parents:
                continue
            rows = json.loads(path.read_text())
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                for key in ("claim", "passage"):
                    if row.get(key):
                        items.append((str(path), key, row[key]))
                for src in row.get("sources") or []:
                    if isinstance(src, dict) and src.get("passage"):
                        items.append((str(path), "source-passage", src["passage"]))
                for atom in row.get("atoms") or []:
                    if atom.get("claim"):
                        items.append((str(path), "atom-claim", atom["claim"]))
                    for src in atom.get("sources") or []:
                        if src.get("passage"):
                            items.append((str(path), "atom-passage", src["passage"]))
                for q_rows in (row.get("queries") or {}).values():
                    for r in q_rows:
                        if r.get("passage"):
                            items.append((str(path), "probe-passage", r["passage"]))
    return items


def main():
    new_rows = json.loads((ROOT / "data/investigations.json").read_text())
    prior = load_prior_claims_and_passages()
    prior_hash_index = {}
    for path, field, text in prior:
        prior_hash_index.setdefault(digest(text), []).append((path, field))

    exact_overlaps = []
    for r in new_rows:
        d = digest(r["claim"])
        if d in prior_hash_index:
            exact_overlaps.append(
                {"new_id": r["id"], "field": "claim", "matched_in": prior_hash_index[d]}
            )
        for s in r["sources"]:
            d = digest(s["passage"])
            if d in prior_hash_index:
                exact_overlaps.append(
                    {
                        "new_id": r["id"],
                        "field": "source-passage",
                        "matched_in": prior_hash_index[d],
                    }
                )

    # Near-duplicate claim check (>=85% word Jaccard) against prior claims only.
    prior_claim_texts = [(p, t) for p, f, t in prior if f in ("claim", "atom-claim")]
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
            if jaccard >= 0.85 and digest(r["claim"]) != digest(text):
                near_dupes.append(
                    {
                        "new_id": r["id"],
                        "matched_in": path,
                        "jaccard": round(jaccard, 3),
                    }
                )

    # Internal duplicate check within the new set itself.
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
    (ROOT / "data" / "investigations-leakage-audit.json").write_text(
        json.dumps(audit, indent=2)
    )
    print("prior_items_scanned:", len(prior))
    print("exact_overlaps:", len(exact_overlaps))
    print("near_duplicate_claims (>=85% jaccard):", len(near_dupes))
    print("internal_duplicates:", len(internal_dupes))
    for n in near_dupes[:20]:
        print(" ", n)
    if exact_overlaps or internal_dupes:
        raise SystemExit("Leakage detected -- resolve before proceeding.")


if __name__ == "__main__":
    main()
