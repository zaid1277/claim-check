"""Warm, uncached NLI/embedding pipeline timing on validation only, without web IO."""

import argparse
import json
import resource
import statistics
import time
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from app.core.settings import Settings
from app.services import pipeline
from app.services.article_extraction import Article
from app.services.embeddings import LocalEmbeddings
from app.services.nli import LocalNLI
from app.services.search import FixtureSearch

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--model", required=True)
parser.add_argument("--output", required=True)
parser.add_argument("--nli-only", action="store_true")
args = parser.parse_args()
settings = Settings(_env_file=None, nli_model=args.model)
nli = LocalNLI(settings.nli_model, settings.min_nli_confidence)
embedding = LocalEmbeddings(settings.embedding_model)
task = "nli" if args.nli_only else "verdicts"
rows = [
    r
    for r in json.loads((root / f"data/{task}.json").read_text())
    if r["split"] == "validation"
]


def run(row):
    if args.nli_only:
        return nli.classify(row["claim"], row["passage"])
    candidates = [
        (
            Article(
                s["url"],
                "Controlled evidence",
                urlsplit(s["url"]).hostname,
                s["passage"],
                s["published_at"],
            ),
            s["passage"],
        )
        for s in row["sources"]
    ]
    with patch.object(pipeline, "collect_evidence", return_value=candidates):
        return pipeline.check_claim(
            row["claim"], settings, FixtureSearch([]), embedding, nli
        )


start = time.perf_counter()
run(rows[0])
warmup = time.perf_counter() - start
elapsed = []
for row in rows:
    start = time.perf_counter()
    run(row)
    elapsed.append(time.perf_counter() - start)
result = dict(
    model=args.model,
    task=task,
    pipeline_file=pipeline.__file__,
    count=len(rows),
    first_investigation_seconds=warmup,
    mean_seconds=statistics.mean(elapsed),
    median_seconds=statistics.median(elapsed),
    peak_rss_bytes_macos=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    note="CPU; web/database excluded; warm models; fresh NLI/embedding inference.",
)
Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
