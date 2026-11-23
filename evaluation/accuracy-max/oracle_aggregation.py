"""Accuracy-max pass, Phase 23 (partial): aggregation-oracle simulation.

Uses ALL controlled cases (not just errors) from both prior holdouts,
diagnostic-only. For each case, re-runs the real `assess()` aggregation
function with pre-NLI gating REMOVED (every evidence item's stance forced
to its raw, ungated NLI label) to answer: if the model's raw judgment were
trusted completely and only the aggregation formula ran, how accurate
would the system be? This isolates "gating cost" from "aggregation-math
cost" -- both currently folded together in end-to-end accuracy.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "api"))

from app.core.settings import get_settings  # noqa: E402
from app.schemas.investigation import Evidence  # noqa: E402
from app.services.evidence_scoring import assess  # noqa: E402

settings = get_settings()


def load_cases(product_path, investigations_path):
    investigations = {
        r["id"]: r for r in json.loads(Path(investigations_path).read_text())
    }
    attempts = [
        json.loads(line)
        for line in Path(product_path).read_text().splitlines()
        if line.strip()
    ]
    by_id = {
        r["case_id"]: r
        for r in attempts
        if r["route"] in ("typed-browser", "typed-api")
    }
    cases = []
    for identifier, inv in investigations.items():
        attempt = by_id.get(identifier)
        if not attempt or not attempt.get("success"):
            continue
        assessments = attempt["result"].get("assessments", [])
        if not assessments:
            continue
        cases.append(
            {
                "id": identifier,
                "claim": inv["claim"],
                "expected": inv["expected"],
                "difficulty": inv["difficulty"],
                "origin": inv["origin"],
                "actual_predicted": assessments[0]["verdict"],
                "evidence": assessments[0]["evidence"],
            }
        )
    return cases


def to_evidence_objects(raw_evidence, use_raw_stance):
    objects = []
    for e in raw_evidence:
        data = dict(e)
        if use_raw_stance and data.get("raw_stance"):
            data["stance"] = data["raw_stance"]
        data.pop("counted", None)
        data.pop("evidence_score", None)
        objects.append(Evidence(evidence_score=0, **data))
    return objects


def run_oracle(cases, use_raw_stance):
    correct = 0
    rows = []
    for case in cases:
        evidence = to_evidence_objects(case["evidence"], use_raw_stance)
        result = assess(case["claim"], evidence, settings)
        is_correct = result.verdict == case["expected"]
        correct += is_correct
        rows.append(
            {
                "id": case["id"],
                "difficulty": case["difficulty"],
                "expected": case["expected"],
                "oracle_predicted": result.verdict,
                "correct": is_correct,
            }
        )
    return correct / len(cases) if cases else 0, rows


def main():
    hyper_root = REPO / "evaluation/hyper/final"
    remediation_root = REPO / "evaluation/remediation/final"
    hyper_cases = load_cases(
        hyper_root / "results/product-controlled.jsonl",
        hyper_root / "data/investigations.json",
    )
    remediation_cases = load_cases(
        remediation_root / "results/product-controlled.jsonl",
        remediation_root / "data/investigations.json",
    )
    all_cases = hyper_cases + remediation_cases
    print(
        f"Total cases with evidence loaded: {len(all_cases)} "
        f"(hyper {len(hyper_cases)} + remediation {len(remediation_cases)})"
    )

    actual_correct = sum(c["actual_predicted"] == c["expected"] for c in all_cases)
    actual_pct = actual_correct / len(all_cases)
    print(
        f"\nActual production accuracy on these cases: "
        f"{actual_correct}/{len(all_cases)} = {actual_pct:.3%}"
    )

    oracle_acc, oracle_rows = run_oracle(all_cases, use_raw_stance=True)
    print(f"Aggregation-oracle (raw NLI, no gating) accuracy: {oracle_acc:.3%}")

    gated_acc, gated_rows = run_oracle(all_cases, use_raw_stance=False)
    print(
        f"Sanity check -- re-running assess() with the ALREADY-gated "
        f"stance stored in evidence (should ~match actual production): {gated_acc:.3%}"
    )

    # By difficulty
    for difficulty in ["easy", "medium", "hard"]:
        subset = [c for c in all_cases if c["difficulty"] == difficulty]
        if not subset:
            continue
        actual = sum(c["actual_predicted"] == c["expected"] for c in subset) / len(
            subset
        )
        oracle, _ = run_oracle(subset, use_raw_stance=True)
        line = (
            f"  {difficulty}: actual={actual:.3%} "
            f"oracle(raw-nli)={oracle:.3%} n={len(subset)}"
        )
        print(line)

    (Path(__file__).parent / "results/aggregation-oracle.json").write_text(
        json.dumps(
            {
                "n_cases": len(all_cases),
                "actual_accuracy": actual_correct / len(all_cases),
                "raw_nli_oracle_accuracy": oracle_acc,
                "gated_sanity_check_accuracy": gated_acc,
                "oracle_rows": oracle_rows,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
