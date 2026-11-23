"""Check corpus counts, grouping and previous-project overlap before locking."""

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def normalize(text):
    return " ".join(text.casefold().rstrip(". ").split())


def claims(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"claim", "hypothesis"} and isinstance(item, str):
                yield normalize(item)
            else:
                yield from claims(item)
    elif isinstance(value, list):
        for item in value:
            yield from claims(item)


prior = set()
for path in ROOT.parent.rglob("*.json"):
    if any(part in {"final", "results", "baseline", ".cache"} for part in path.parts):
        continue
    prior.update(claims(json.loads(path.read_text())))
nli = json.loads((ROOT / "data/nli.json").read_text())
verdicts = json.loads((ROOT / "data/verdicts.json").read_text())
assert len(nli) >= 500 and len(verdicts) >= 150
assert not (set(claims(nli)) & prior)
assert not (set(claims(verdicts)) & prior)
assert not (set(claims(nli)) & set(claims(verdicts)))
groups = {}
for row in nli:
    groups.setdefault(row["group"], set()).add(row["split"])
assert all(len(splits) == 1 for splits in groups.values())
counts = Counter(row["label"] for row in nli)
assert len(set(counts.values())) == 1
result = dict(
    nli=len(nli),
    nli_labels=dict(counts),
    nli_splits=dict(Counter(r["split"] for r in nli)),
    investigations=len(verdicts),
    difficulty=dict(Counter(r["difficulty"] for r in verdicts)),
    prior_unique_claims=len(prior),
    exact_overlap=0,
    group_leakage=0,
    caveat=(
        "Exact text/group checks do not prove absence of semantic "
        "or model-pretraining overlap."
    ),
)
(ROOT / "data/split-audit.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
