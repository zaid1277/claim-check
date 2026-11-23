"""NLI upgrade pass, Phase 16: development-only pipeline integration test.

Reuses evaluation/hyper/replay_controlled.py (already-validated, fast
in-process replay of the 175-case original development benchmark --
evaluation/final/data/verdicts.json, explicitly development data, NOT
either of the two protected independent holdouts) to compare the CURRENT
production NLI model against the new candidate with everything else
(retrieval, cross-encoder, source weights, aggregation, relevance
weighting, claim-risk logic, verdict rules) held fixed, per phase 19.

Does NOT overwrite production settings -- both runs use explicit,
separate Settings objects; the candidate is never written to
api/app/core/settings.py by this script.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "api"))
sys.path.insert(0, str(REPO / "evaluation/hyper"))
ROOT = Path(__file__).resolve().parent

import replay_controlled  # noqa: E402

from app.core.settings import Settings  # noqa: E402


def main():
    current_settings = Settings(_env_file=None)
    print(f"Current production NLI model: {current_settings.nli_model}")
    current_results = replay_controlled.run(settings=Settings(_env_file=None))
    current_summary = replay_controlled.summarize(current_results)
    print("Current NLI pipeline replay:")
    print(json.dumps(current_summary, indent=2))

    candidate_path = str(ROOT / "results/lora-base-256-merged")
    if not Path(candidate_path).exists():
        raise SystemExit(
            f"Merged candidate model not found at {candidate_path} -- "
            "run merge_lora.py first."
        )
    candidate_settings = Settings(_env_file=None)
    candidate_settings.nli_model = candidate_path
    print(f"\nCandidate NLI model: {candidate_path}")
    candidate_results = replay_controlled.run(settings=candidate_settings)
    candidate_summary = replay_controlled.summarize(candidate_results)
    print("Candidate NLI pipeline replay:")
    print(json.dumps(candidate_summary, indent=2))

    (ROOT / "results/pipeline-integration.json").write_text(
        json.dumps(
            {
                "current": {"summary": current_summary, "rows": current_results},
                "candidate": {"summary": candidate_summary, "rows": candidate_results},
            },
            indent=2,
        )
    )
    print("\n=== Comparison ===")
    print(f"{'Metric':<22}{'Current':>12}{'Candidate':>12}")
    for key in ["accuracy", "coverage", "selective_accuracy"]:
        c = current_summary[key] or 0
        n = candidate_summary[key] or 0
        print(f"{key:<22}{c:>12.3%}{n:>12.3%}")
    for d in ["easy", "medium", "hard"]:
        c = current_summary["by_difficulty"][d]["accuracy"] or 0
        n = candidate_summary["by_difficulty"][d]["accuracy"] or 0
        print(f"{d + '_accuracy':<22}{c:>12.3%}{n:>12.3%}")
    for key in ["false_abstentions", "confident_errors"]:
        print(f"{key:<22}{current_summary[key]:>12}{candidate_summary[key]:>12}")


if __name__ == "__main__":
    main()
