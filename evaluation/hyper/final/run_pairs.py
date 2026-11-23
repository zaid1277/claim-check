"""Use the same scorer as Pass 2/final, with separate data, cache and holdout guard."""

import hashlib
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1] / "pass2"))
experiment = importlib.import_module("experiment")

original_metrics = experiment.metrics
experiment.metrics = lambda rows, labels: (
    original_metrics(rows, labels) if rows else {"count": 0}
)
experiment.ROOT = ROOT
experiment.CACHE = ROOT / ".cache"
experiment.CACHE.mkdir(exist_ok=True)
if "--split" in sys.argv and sys.argv[sys.argv.index("--split") + 1] in {"test", "all"}:
    if not (ROOT / "lock.json").exists():
        raise SystemExit("Final inference is forbidden until lock.json exists.")
    lock = json.loads((ROOT / "lock.json").read_text())
    for name, expected in lock["files"].items():
        if (
            hashlib.sha256((ROOT.parents[2] / name).read_bytes()).hexdigest()
            != expected
        ):
            raise SystemExit(f"Frozen file changed: {name}")
    output = Path(sys.argv[sys.argv.index("--output") + 1])
    if output.exists():
        raise SystemExit("Final output already exists; do not rerun the holdout.")
    original_probabilities = experiment.CachedNLI.probabilities

    def checkpoint(self, claim, passage):
        value = original_probabilities(self, claim, passage)
        self.save()
        return value

    experiment.CachedNLI.probabilities = checkpoint
experiment.main()
