"""Group 4, phase 2: select fresh ANLI premises for the new Hyper NLI
holdout, with no overlap against ANY prior corpus in this repo (original
Pass 2, the old final corpus, and every nli.json anywhere under evaluation/).

Same methodology as evaluation/final/build_nli.py (already validated by
this project), applied to mine a second, disjoint batch from the same
2400-pair ANLI source pool (only 600 of 2400 were used previously).
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
    per_label_target = 240  # 240*3 = 720 pairs, comfortably above the 600 minimum
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
        i = counts[label]
        # 60 development / 60 validation / 120 test per label -> 180/180/360
        # overall, comfortably exceeding the 300-held-out minimum.
        split = "development" if i < 60 else "validation" if i < 120 else "test"
        result.append(
            dict(
                id="hyper-anli-" + row["uid"],
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
    if any(c < per_label_target for c in counts.values()):
        raise SystemExit(f"Pool exhausted before reaching target: {dict(counts)}")
    target = ROOT / "data/nli-mined.json"
    target.write_text(json.dumps(result, indent=2) + "\n")
    print("Selected counts:", dict(Counter((r["split"], r["label"]) for r in result)))
    print("Total:", len(result))
    print("SHA256:", hashlib.sha256(target.read_bytes()).hexdigest())


if __name__ == "__main__":
    build()
