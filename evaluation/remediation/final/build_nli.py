"""Remediation pass 5, part 17: select fresh ANLI premises for the NEW
confirmation-holdout NLI set, with no overlap against ANY prior corpus in
this repo -- original Pass 2, the old final corpus, the Group 4 Hyper
holdout, AND the Part 2 multi-fold contradiction-calibration corpus this
same remediation pass built and tuned on (evaluation/remediation/data/
contradiction-corpus.json + contradiction-authored.json). Per part 16/17,
this confirmation set must be unseen during every development decision made
this pass, so it excludes that corpus too even though it is itself new.

Same methodology as evaluation/hyper/final/build_nli.py (already validated),
mining a third, disjoint batch from the same 2400-pair ANLI source pool.
Of 2400: 600 consumed by pass2, 720 by the Group 4 Hyper holdout, 600 by
this pass's own contradiction-corpus.json -- ~480 remain.
"""

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVAL_ROOT = ROOT.parents[1]  # evaluation/


def digest(text):
    return hashlib.sha256(" ".join(text.casefold().split()).encode()).hexdigest()


def build():
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
            if "passage" in row:
                seen.add(digest(row["passage"]))
            if "claim" in row:
                seen.add(digest(row["claim"]))
    # This pass's own multi-fold contradiction-calibration corpus (part 2)
    # and authored stress-test pairs -- tuned on this pass, so must be
    # excluded from the confirmation holdout (part 16/17) even though both
    # are new.
    for name in ["contradiction-corpus.json", "contradiction-authored.json"]:
        path = ROOT.parent / "data" / name
        if path.exists():
            for row in json.loads(path.read_text()):
                if row.get("passage"):
                    seen.add(digest(row["passage"]))
                if row.get("claim"):
                    seen.add(digest(row["claim"]))
    for path in EVAL_ROOT.glob("**/missed-contradictions-pairs.json"):
        for row in json.loads(path.read_text()):
            if row.get("passage"):
                seen.add(digest(row["passage"]))
            if row.get("claim"):
                seen.add(digest(row["claim"]))
    for pattern in [
        "**/retrieval-probes.json",
        "**/compound-probes.json",
        "**/verdicts.json",
    ]:
        for path in EVAL_ROOT.glob(pattern):
            rows = json.loads(path.read_text())
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                if row.get("claim"):
                    seen.add(digest(row["claim"]))
                for src in row.get("sources") or []:
                    if src.get("passage"):
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

    candidates = json.loads((EVAL_ROOT / "final/data/anli-source.json").read_text())
    # The pool is nearly exhausted after pass2 + the Hyper holdout + this
    # pass's own dev corpus: take everything remaining per label rather than
    # capping uniformly at the scarcest label's ceiling, then top up to a
    # balanced 250+ total with the authored facts in build_and_audit_nli.py.
    per_label_max = {"support": 72, "neutral": 47, "contradict": 41}
    counts = Counter()
    result = []
    for row in sorted(candidates, key=lambda r: digest(r["premise"] + r["hypothesis"])):
        label = {0: "support", 1: "neutral", 2: "contradict"}[row["label"]]
        if (
            counts[label] >= per_label_max[label]
            or digest(row["premise"]) in seen
            or digest(row["hypothesis"]) in seen
        ):
            continue
        seen.update([digest(row["premise"]), digest(row["hypothesis"])])
        # Confirmation holdout is entirely test-split (no dev/validation
        # slicing needed -- run once, no threshold tuning against it).
        split = "test"
        result.append(
            dict(
                id="remediation-anli-" + row["uid"],
                group=digest(row["premise"]),
                split=split,
                claim=row["hypothesis"],
                passage=row["premise"],
                label=label,
                domain="ANLI-unannotated",
                tag=row["source_split"],
                published_at=None,
                origin="ANLI",
            )
        )
        counts[label] += 1
    if any(counts[label] < per_label_max[label] for label in per_label_max):
        raise SystemExit(f"Pool exhausted before reaching target: {dict(counts)}")
    target = ROOT / "data/nli-mined.json"
    target.write_text(json.dumps(result, indent=2) + "\n")
    print("Selected counts:", dict(Counter((r["split"], r["label"]) for r in result)))
    print("Total:", len(result))
    print("SHA256:", hashlib.sha256(target.read_bytes()).hexdigest())


if __name__ == "__main__":
    build()
