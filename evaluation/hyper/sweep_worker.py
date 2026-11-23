"""One-shot worker: run the 175-case replay at a single minimum_evidence
value and write its own result file, so a sweep can run in parallel across
CPU cores instead of serially."""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "api"))
sys.path.insert(0, str(REPO / "evaluation/hyper"))

import replay_controlled as rc  # noqa: E402

from app.core.settings import Settings  # noqa: E402

if __name__ == "__main__":
    min_ev = float(sys.argv[1])
    settings = Settings(_env_file=None)
    settings.minimum_evidence = min_ev
    results = rc.run(settings=settings)
    summary = rc.summarize(results)
    out = REPO / f"evaluation/hyper/sweep-{min_ev}.json"
    out.write_text(
        json.dumps({"minimum_evidence": min_ev, "summary": summary}, indent=2)
    )
    print(f"done {min_ev}")
