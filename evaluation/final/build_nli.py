"""Select fresh ANLI premises, with no overlap across projects or splits."""

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def digest(text):
    return hashlib.sha256(" ".join(text.casefold().split()).encode()).hexdigest()


def build():
    old = json.loads((ROOT.parent / "pass2/data/anli-source.json").read_text())
    seen = {digest(r["premise"]) for r in old}
    for path in ROOT.parent.glob("**/nli.json"):
        if ROOT in path.parents:
            continue
        rows = json.loads(path.read_text())
        if not isinstance(rows, list):
            continue
        for row in rows:
            seen.add(digest(row["passage"]))
            seen.add(digest(row["claim"]))
    candidates = json.loads((ROOT / "data/anli-source.json").read_text())
    counts = Counter()
    result = []
    for row in sorted(candidates, key=lambda r: digest(r["premise"] + r["hypothesis"])):
        label = {0: "support", 1: "neutral", 2: "contradict"}[row["label"]]
        if (
            counts[label] == 200
            or digest(row["premise"]) in seen
            or digest(row["hypothesis"]) in seen
        ):
            continue
        seen.update([digest(row["premise"]), digest(row["hypothesis"])])
        i = counts[label]
        result.append(
            dict(
                id="final-anli-" + row["uid"],
                group=digest(row["premise"]),
                split="development" if i < 60 else "validation" if i < 100 else "test",
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
    assert counts == {"support": 200, "neutral": 200, "contradict": 200}, counts
    target = ROOT / "data/nli.json"
    target.write_text(json.dumps(result, indent=2) + "\n")
    print("Selected counts:", dict(Counter((r["split"], r["label"]) for r in result)))
    print("SHA256:", hashlib.sha256(target.read_bytes()).hexdigest())


if __name__ == "__main__":
    build()
