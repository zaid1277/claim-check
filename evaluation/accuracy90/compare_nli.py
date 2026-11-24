"""Compare three-way NLI candidates on development data, never final holdouts.

Run one model per process to bound memory. Uses the production premise order,
normalization and token limit; reports raw and confidence-gated labels separately.
"""

import argparse
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "api"))
sys.path.insert(0, str(REPO / "evaluation/pass2"))

from experiment import metrics  # noqa: E402

from app.core.settings import Settings  # noqa: E402
from app.services.nli import LocalNLI, load_nli  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to overwrite an existing measurement.")
    data = REPO / "evaluation/nli-upgrade/data/validation.json"
    rows = json.loads(data.read_text())
    settings = Settings(_env_file=None)
    provider = LocalNLI(args.model, 0.0)
    _, model = load_nli(args.model)
    raw, gated, elapsed = [], [], []
    for index, row in enumerate(rows):
        start = time.perf_counter()
        stance, confidence = provider.classify(row["claim"], row["passage"])
        elapsed.append(time.perf_counter() - start)
        record = {
            "id": row["id"],
            "expected": row["label"],
            "predicted": stance,
            "confidence": confidence,
            "origin": row.get("origin"),
        }
        raw.append(record)
        gated.append(
            {
                **record,
                "predicted": stance
                if confidence >= settings.min_nli_confidence
                else "neutral",
            }
        )
        if (index + 1) % 50 == 0:
            print(f"{index + 1}/{len(rows)} pairs", flush=True)
    labels = ["support", "contradict", "neutral"]
    report = {
        "model": args.model,
        "revision": getattr(model.config, "_commit_hash", None),
        "id2label": model.config.id2label,
        "dataset": str(data.relative_to(REPO)),
        "dataset_sha256": hashlib.sha256(data.read_bytes()).hexdigest(),
        "scope": "Reused development validation; not independent test accuracy",
        "max_tokens": settings.nli_max_tokens,
        "confidence_threshold": settings.min_nli_confidence,
        "raw": metrics(raw, labels),
        "gated": metrics(gated, labels),
        "scientific_raw": metrics(
            [r for r in raw if r["origin"] == "SciFact-train"], labels
        ),
        "median_ms": 1000 * statistics.median(elapsed),
        "p95_ms": 1000 * sorted(elapsed)[int(0.95 * (len(elapsed) - 1))],
        "rows": raw,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
