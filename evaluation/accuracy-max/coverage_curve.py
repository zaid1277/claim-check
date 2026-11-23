"""Accuracy-max pass, Phase 22: coverage vs accuracy / selective-accuracy
curve, computed by re-running the real `aggregate()` function at swept
`minimum_evidence` values over the SAME already-recorded evidence from
both prior holdouts (diagnostic-only; no re-collection, no re-tuning of
the shipped setting from this sweep)."""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "api"))

from app.core.settings import get_settings  # noqa: E402
from app.schemas.investigation import Evidence  # noqa: E402
from app.services.evidence_scoring import assess  # noqa: E402

settings = get_settings()


def load_cases():
    cases = []
    for root in [
        REPO / "evaluation/hyper/final",
        REPO / "evaluation/remediation/final",
    ]:
        investigations = {
            r["id"]: r
            for r in json.loads((root / "data/investigations.json").read_text())
        }
        attempts = [
            json.loads(line)
            for line in (root / "results/product-controlled.jsonl")
            .read_text()
            .splitlines()
            if line.strip()
        ]
        by_id = {
            r["case_id"]: r
            for r in attempts
            if r["route"] in ("typed-browser", "typed-api")
        }
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
                    "evidence": assessments[0]["evidence"],
                }
            )
    return cases


def to_evidence_objects(raw_evidence):
    objects = []
    for e in raw_evidence:
        data = dict(e)
        data.pop("counted", None)
        data.pop("evidence_score", None)
        objects.append(Evidence(evidence_score=0, **data))
    return objects


def sweep(cases, thresholds):
    results = []
    for t in thresholds:
        swept_settings = settings.model_copy(update={"minimum_evidence": t})
        outcomes = []
        for case in cases:
            evidence = to_evidence_objects(case["evidence"])
            result = assess(case["claim"], evidence, swept_settings)
            outcomes.append((result.verdict, case["expected"]))
        total = len(outcomes)
        decided = [o for o in outcomes if o[0] != "INSUFFICIENT_EVIDENCE"]
        accuracy = sum(p == e for p, e in outcomes) / total
        coverage = len(decided) / total
        selective = sum(p == e for p, e in decided) / len(decided) if decided else None
        results.append(
            {
                "minimum_evidence": t,
                "accuracy": accuracy,
                "coverage": coverage,
                "selective_accuracy": selective,
            }
        )
    return results


def main():
    cases = load_cases()
    print(f"Loaded {len(cases)} cases (both holdouts combined, diagnostic use only)")
    thresholds = [
        0.05,
        0.10,
        0.15,
        0.20,
        0.25,
        0.30,
        0.40,
        0.50,
        0.65,
        0.80,
        1.00,
        1.30,
        1.60,
        2.00,
    ]
    results = sweep(cases, thresholds)
    print(f"\n{'min_evidence':>12} {'accuracy':>10} {'coverage':>10} {'selective':>10}")
    for r in results:
        sel = (
            f"{r['selective_accuracy']:.3%}"
            if r["selective_accuracy"] is not None
            else "n/a"
        )
        line = (
            f"{r['minimum_evidence']:>12.2f} {r['accuracy']:>10.3%} "
            f"{r['coverage']:>10.3%} {sel:>10}"
        )
        print(line)

    # Named operating points requested: coverage ~100/90/80/70%
    print("\nNearest operating points to requested coverage levels:")
    for target_coverage in [1.00, 0.90, 0.80, 0.70]:
        closest = min(results, key=lambda r: abs(r["coverage"] - target_coverage))
        print(
            f"  coverage~{target_coverage:.0%}: "
            f"min_evidence={closest['minimum_evidence']:.2f} "
            f"actual_coverage={closest['coverage']:.3%} "
            f"accuracy={closest['accuracy']:.3%} "
            f"selective={closest['selective_accuracy']:.3%}"
        )

    (Path(__file__).parent / "results/coverage-curve.json").write_text(
        json.dumps(results, indent=2)
    )


if __name__ == "__main__":
    main()
