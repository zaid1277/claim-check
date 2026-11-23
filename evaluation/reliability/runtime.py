"""Single-model, warm CPU timing on the same validation pairs; no web requests."""

import argparse
import json
import platform
import resource
import statistics
import time
from pathlib import Path

from app.services.nli import LocalNLI, load_nli

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--model", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parent
pairs = [
    r
    for r in json.loads((root / "data/nli.json").read_text())
    if r["split"] == "validation"
]
nli = LocalNLI(args.model, 0.65)
start = time.perf_counter()
nli.classify(pairs[0]["claim"], pairs[0]["passage"])
startup = time.perf_counter() - start
elapsed = []
for row in pairs:
    start = time.perf_counter()
    nli.classify(row["claim"], row["passage"])
    elapsed.append(time.perf_counter() - start)
_, model = load_nli(args.model)
report = dict(
    model=args.model,
    revision=model.config._commit_hash,
    label_mapping=model.config.id2label,
    platform=platform.platform(),
    pairs=len(pairs),
    first_call_seconds=startup,
    mean_seconds=statistics.mean(elapsed),
    median_seconds=statistics.median(elapsed),
    peak_process_rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    rss_units="bytes on macOS; KiB on Linux",
)
Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
