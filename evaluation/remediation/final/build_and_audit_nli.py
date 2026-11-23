"""Remediation pass 5, part 17: merge mined ANLI pairs + generated pairs
(from confirmation-nli-facts.json) into the confirmation-holdout NLI set,
then run and document the independence/leakage audit against every prior
corpus in this repo, INCLUDING the Group 4 Hyper holdout and this pass's
own multi-fold contradiction-calibration corpus (never a tuning target, but
still must not leak into the confirmation set -- part 16/17).
"""

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVAL_ROOT = ROOT.parents[1]


def norm(text):
    return " ".join(text.casefold().split())


def digest(text):
    return hashlib.sha256(norm(text).encode()).hexdigest()


def load_prior_texts():
    """Every claim/passage/premise/hypothesis string from every prior
    corpus and probe set in this repo, for the leakage audit."""
    texts = []
    for path in EVAL_ROOT.glob("**/nli.json"):
        if ROOT in path.parents or path.parent == ROOT:
            continue
        rows = json.loads(path.read_text())
        if isinstance(rows, list):
            for r in rows:
                if isinstance(r, dict):
                    for k in ("claim", "passage"):
                        if r.get(k):
                            texts.append((str(path), k, r[k]))
    # Note: the raw ANLI source pools (evaluation/final/data/anli-source.json
    # and evaluation/pass2/data/anli-source.json) are deliberately NOT
    # scanned here. build_nli.py already excludes every premise in both
    # pools from selection at construction time (so this holdout's mined
    # rows are guaranteed disjoint from anything either pool's premises were
    # used for) -- scanning the raw pool here would flag every mined row as
    # "overlapping" with the very pool it was legitimately drawn from, which
    # is not leakage. What matters for leakage is overlap with corpora that
    # were actually CONSUMED into a prior project's nli.json/verdicts/probes,
    # which is what the checks below cover.
    for path in EVAL_ROOT.glob("**/verdicts.json"):
        rows = json.loads(path.read_text())
        if not isinstance(rows, list):
            continue
        for r in rows:
            if not isinstance(r, dict):
                continue
            if r.get("claim"):
                texts.append((str(path), "claim", r["claim"]))
            for src in r.get("sources") or []:
                if src.get("passage"):
                    texts.append((str(path), "source-passage", src["passage"]))
    for pattern in ["**/retrieval-probes.json", "**/compound-probes.json"]:
        for path in EVAL_ROOT.glob(pattern):
            rows = json.loads(path.read_text())
            for r in rows:
                if r.get("claim"):
                    texts.append((str(path), "probe-claim", r["claim"]))
                for atom in r.get("atoms") or []:
                    if atom.get("claim"):
                        texts.append((str(path), "probe-atom-claim", atom["claim"]))
                    for src in atom.get("sources") or []:
                        if src.get("passage"):
                            texts.append((str(path), "probe-passage", src["passage"]))
                for q_rows in (r.get("queries") or {}).values():
                    for row in q_rows:
                        if row.get("passage"):
                            texts.append((str(path), "probe-passage", row["passage"]))
    for path in EVAL_ROOT.glob("**/missed-contradictions-pairs.json"):
        for r in json.loads(path.read_text()):
            if r.get("claim"):
                texts.append((str(path), "missed-claim", r["claim"]))
            if r.get("passage"):
                texts.append((str(path), "missed-passage", r["passage"]))
    # This pass's own multi-fold contradiction-calibration corpus -- new,
    # but consumed for development/tuning decisions this pass, so it must
    # not leak into the confirmation holdout either (part 16/17).
    for name in ["contradiction-corpus.json", "contradiction-authored.json"]:
        path = EVAL_ROOT / "remediation/data" / name
        if path.exists():
            for r in json.loads(path.read_text()):
                if r.get("claim"):
                    texts.append((str(path), "dev-claim", r["claim"]))
                if r.get("passage"):
                    texts.append((str(path), "dev-passage", r["passage"]))
    return texts


def generate_from_facts():
    """Turn each fact/alternative/unrelated triple into a support,
    contradict, and neutral NLI pair (same lightweight construction as the
    Group 4 facts.json corpus)."""
    facts = json.loads((ROOT / "data/confirmation-nli-facts.json").read_text())
    rows = []
    for f in facts:
        passage = f["fact"] + " This is a well-documented, widely reported fact."
        for suffix, claim, label in [
            ("support", f["fact"], "support"),
            ("contradict", f["alternative"], "contradict"),
            ("neutral", f["unrelated"], "neutral"),
        ]:
            rows.append(
                dict(
                    id=f["id"] + "-" + suffix,
                    group=digest(f["fact"]),
                    split="test",
                    claim=claim,
                    passage=passage,
                    label=label,
                    domain=f["domain"],
                    tag="remediation-confirmation-authored",
                    published_at=None,
                    origin="authored",
                )
            )
    return rows


def main():
    mined = json.loads((ROOT / "data/nli-mined.json").read_text())
    authored = generate_from_facts()
    for r in mined:
        r["origin"] = "ANLI"

    combined = mined + authored

    # Internal near-duplicate check (exact normalized text match) within the
    # new holdout itself. Claim-only: the generated facts pairs deliberately
    # reuse one passage across its support/contradict/neutral triple (the
    # `group` field records this, same pattern ANLI itself uses for
    # multiple hypotheses per premise) -- that is not leakage, only reused
    # claim text across genuinely different rows would be.
    internal_seen = {}
    internal_dupes = []
    for r in combined:
        d = digest(r["claim"])
        if d in internal_seen and internal_seen[d] != r["id"]:
            internal_dupes.append((r["id"], internal_seen[d], "claim"))
        internal_seen[d] = r["id"]

    # External audit against every prior corpus.
    prior = load_prior_texts()
    prior_hashes = {digest(text): (path, field) for path, field, text in prior}
    exact_overlaps = []
    for r in combined:
        for k in ("claim", "passage"):
            d = digest(r[k])
            if d in prior_hashes:
                exact_overlaps.append(
                    {"new_id": r["id"], "field": k, "matched_in": prior_hashes[d][0]}
                )

    # Normalized-claim overlap (already covered by exact match above, since
    # digest() itself normalizes case/whitespace) -- report word-level
    # near-duplicates (>=90% Jaccard) as a softer, documented check.
    def words(t):
        return set(norm(t).split())

    near_dupes = []
    prior_claims = [
        (p, t) for p, f, t in prior if f in ("claim", "hypothesis", "probe-claim")
    ]
    for r in combined:
        rw = words(r["claim"])
        if not rw:
            continue
        for path, text in prior_claims:
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

    audit = {
        "combined_count": len(combined),
        "by_split": dict(Counter(r["split"] for r in combined)),
        "by_label": dict(Counter(r["label"] for r in combined)),
        "internal_near_duplicates": internal_dupes,
        "exact_overlap_with_prior_corpora": exact_overlaps,
        "near_duplicate_claims_with_prior_corpora": near_dupes,
        "prior_texts_scanned": len(prior),
    }
    (ROOT / "data" / "nli-leakage-audit.json").write_text(json.dumps(audit, indent=2))
    print(
        json.dumps(
            {k: v for k, v in audit.items() if not isinstance(v, list) or len(v) < 20},
            indent=2,
        )
    )
    print("internal_near_duplicates:", len(internal_dupes))
    print("exact_overlap_with_prior_corpora:", len(exact_overlaps))
    print("near_duplicate_claims_with_prior_corpora:", len(near_dupes))

    if internal_dupes or exact_overlaps:
        raise SystemExit(
            "Leakage detected -- resolve before writing the final nli.json. "
            "See data/nli-leakage-audit.json."
        )

    (ROOT / "data" / "nli.json").write_text(json.dumps(combined, indent=2) + "\n")
    print(f"\nWrote {len(combined)} pairs to data/nli.json")
    print("SHA256:", hashlib.sha256((ROOT / "data/nli.json").read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
