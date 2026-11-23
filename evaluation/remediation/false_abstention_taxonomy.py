"""Remediation pass 5, part 7: classify every false abstention in the
DIAGNOSTIC (never re-tuned-on) Group 4 Hyper holdout into the fine-grained
causes the remediation instructions ask for. Diagnostic use of this holdout
is explicitly permitted (part 16); no threshold or code decision is made
FROM these specific 41 cases -- they only motivate which general mechanism
to inspect, and any change is validated on new development data (part 8-9).
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "api"))

from app.core.settings import get_settings  # noqa: E402
from app.services.claim_risk import claim_risk  # noqa: E402

HYPER = REPO / "evaluation/hyper/final/results/investigation-errors.json"
settings = get_settings()


def classify(row):
    evidence = row["evidence"]
    risk = claim_risk(row.get("id", "") and _claim_for(row))
    counted = [e for e in evidence if e["counted"]]
    support = sum(e["evidence_score"] for e in counted if e["stance"] == "support")
    contradict = sum(
        e["evidence_score"] for e in counted if e["stance"] == "contradict"
    )
    total = support + contradict
    independent = len({e["independence_group"] for e in counted})
    minimum_evidence = (
        settings.high_risk_minimum_evidence
        if risk == "high"
        else settings.minimum_evidence
    )

    if not evidence:
        return "missing-retrieval"
    if not counted:
        # every candidate was neutral or excluded before aggregation
        reasons = [e.get("exclusion_reason") or "" for e in evidence]
        if any(
            "relevance" in r.lower() or "irrelevance floor" in r.lower()
            for r in reasons
        ):
            return "relevance-score-too-low"
        if any("contradiction confidence" in r.lower() for r in reasons):
            return "nli-confidence-gate"
        if any(e["raw_stance"] == "neutral" for e in evidence):
            return "nli-raw-neutral"
        return "relevance-score-too-low"
    if total < minimum_evidence:
        return "evidence-minimum-not-met"
    if risk == "high" and independent < settings.high_risk_min_independent_sources:
        return "claim-risk-independent-source-restriction"
    if support and contradict:
        return "source-conflict-mixed-not-triggered"
    return "aggregation-other"


def _claim_for(case_id):
    # investigation-errors.json doesn't carry the raw claim text; atomic_claim
    # on each evidence item does, which is what claim_risk() needs.
    return None


def main():
    errors = json.loads(HYPER.read_text())
    false_abstentions = [
        e
        for e in errors
        if e["predicted"] == "INSUFFICIENT_EVIDENCE"
        and e["expected"] != "INSUFFICIENT_EVIDENCE"
    ]
    from collections import Counter

    counts = Counter()
    detail = []
    for row in false_abstentions:
        evidence = row["evidence"]
        claim_text = evidence[0]["atomic_claim"] if evidence else ""
        risk = claim_risk(claim_text)
        counted = [e for e in evidence if e["counted"]]
        support = sum(e["evidence_score"] for e in counted if e["stance"] == "support")
        contradict = sum(
            e["evidence_score"] for e in counted if e["stance"] == "contradict"
        )
        total = support + contradict
        independent = len({e["independence_group"] for e in counted})
        minimum_evidence = (
            settings.high_risk_minimum_evidence
            if risk == "high"
            else settings.minimum_evidence
        )
        if not evidence:
            cause = "missing-retrieval"
        elif not counted:
            reasons = [e.get("exclusion_reason") or "" for e in evidence]
            if any("irrelevance floor" in r.lower() for r in reasons):
                cause = "relevance-score-too-low"
            elif any("contradiction confidence" in r.lower() for r in reasons):
                cause = "nli-confidence-gate"
            elif any(e["raw_stance"] == "neutral" for e in evidence):
                cause = "nli-raw-neutral"
            elif any("duplicate" in r.lower() for r in reasons):
                cause = "source-independence-penalty"
            else:
                cause = "relevance-score-too-low"
        elif total < minimum_evidence:
            cause = (
                "claim-risk-high-evidence-minimum"
                if risk == "high"
                else "evidence-minimum-not-met"
            )
        elif (
            risk == "high" and independent < settings.high_risk_min_independent_sources
        ):
            cause = "claim-risk-independent-source-restriction"
        elif support and contradict:
            cause = "source-conflict-mixed-not-triggered"
        else:
            cause = "aggregation-other"
        counts[cause] += 1
        detail.append(
            {
                "id": row["id"],
                "cause": cause,
                "risk": risk,
                "support": round(support, 3),
                "contradict": round(contradict, 3),
                "total": round(total, 3),
                "minimum_evidence": minimum_evidence,
                "independent_sources": independent,
                "n_evidence": len(evidence),
                "n_counted": len(counted),
            }
        )
    out = {"total": len(false_abstentions), "by_cause": dict(counts), "detail": detail}
    (Path(__file__).parent / "results/false-abstention-taxonomy.json").write_text(
        json.dumps(out, indent=2)
    )
    print("Total false abstentions:", len(false_abstentions))
    for cause, n in (
        counts.most_common() if hasattr(counts, "most_common") else counts.items()
    ):
        print(f"  {cause}: {n} ({100 * n / len(false_abstentions):.1f}%)")


if __name__ == "__main__":
    main()
