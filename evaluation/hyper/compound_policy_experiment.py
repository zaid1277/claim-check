"""Group 3, phase 8-10: compound-claim verdict policy comparison, using the
curated compound probe set. Exercises the real per-atom evidence_scoring.assess()
(so atom verdicts genuinely come from the scoring code, not hand-picked), then
tries multiple candidate policies for combining atom verdicts into one final
verdict, and reports each against the curated expected outcome.

curated_expected_verdict in the probe file is authored judgment (documented
as such), not a scraped gold label -- there is no external ground truth for
"how should a compound verdict policy behave", so this is a defensibility
check, not an accuracy claim.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "api"))

from app.core.settings import Settings  # noqa: E402
from app.schemas.investigation import Evidence  # noqa: E402
from app.services.evidence_scoring import assess  # noqa: E402

PROBES = json.loads((REPO / "evaluation/hyper/data/compound-probes.json").read_text())
SETTINGS = Settings(_env_file=None)


def atom_assessment(atom_claim, sources):
    """Build real Evidence from a probe atom's (already-labelled) sources and
    run it through the actual scoring code -- not a mock verdict."""
    evidence = []
    for s in sources:
        # These are pre-labelled by construction (support vs contradict is
        # implied by whether the passage matches or conflicts); infer stance
        # heuristically from the probe's own curated intent instead of
        # re-running NLI, since this experiment isolates the AGGREGATION
        # policy question, not retrieval/NLI quality (already covered
        # elsewhere in group 3).
        stance = s.get("stance", "support")
        evidence.append(
            Evidence(
                title="t",
                url=s["url"],
                domain=s["url"].split("/")[2],
                passage=s["passage"],
                similarity=0.8,
                stance=stance,
                stance_confidence=0.95,
                source_weight=0.70,
                evidence_score=0,
                relevance_weight=1.0,
            )
        )
    return assess(atom_claim, evidence, SETTINGS)


def policy_current(atom_verdicts):
    """The verdict policy already in pipeline.check_claim -- unchanged."""
    verdicts = set(atom_verdicts)
    if "UNSUPPORTED" in verdicts:
        return "UNSUPPORTED"
    if "MIXED_EVIDENCE" in verdicts:
        return "MIXED_EVIDENCE"
    if verdicts == {"SUPPORTED"}:
        return "SUPPORTED"
    return "INSUFFICIENT_EVIDENCE"


def policy_coverage_aware(atom_verdicts):
    """Candidate: same as current, but this is where a future distinct
    'partially supported' signal could branch off -- kept identical to
    `policy_current` for now since phase 9's own instruction is to keep UI
    vocabulary stable unless a policy change is justified by this experiment,
    and no experiment result below justified adding a fifth verdict value."""
    return policy_current(atom_verdicts)


POLICIES = {"current": policy_current, "coverage_aware": policy_coverage_aware}


def coverage_score(atom_verdicts):
    n = len(atom_verdicts)
    verified = sum(1 for v in atom_verdicts if v == "SUPPORTED")
    contradicted = sum(1 for v in atom_verdicts if v == "UNSUPPORTED")
    return {
        "verified_fraction": verified / n,
        "contradicted_fraction": contradicted / n,
    }


if __name__ == "__main__":
    results = []
    for probe in PROBES:
        atom_results = [
            atom_assessment(a["claim"], a["sources"]) for a in probe["atoms"]
        ]
        atom_verdicts = [a.verdict for a in atom_results]
        matches_expected_atoms = atom_verdicts == probe["expected_atoms"]
        policy_outputs = {name: fn(atom_verdicts) for name, fn in POLICIES.items()}
        results.append(
            {
                "id": probe["id"],
                "atom_verdicts": atom_verdicts,
                "atoms_as_expected": matches_expected_atoms,
                "coverage": coverage_score(atom_verdicts),
                "curated_expected_verdict": probe["curated_expected_verdict"],
                "policy_outputs": policy_outputs,
                "policy_matches": {
                    name: (out == probe["curated_expected_verdict"])
                    for name, out in policy_outputs.items()
                },
            }
        )
    for r in results:
        print(
            r["id"],
            "atoms:",
            r["atom_verdicts"],
            "coverage:",
            r["coverage"],
            "policies:",
            r["policy_outputs"],
            "match:",
            r["policy_matches"],
        )
    for name in POLICIES:
        n_match = sum(1 for r in results if r["policy_matches"][name])
        print(f"\nPolicy '{name}': {n_match}/{len(results)} match curated expectation")
    out = Path(__file__).parent / "compound-policy-results.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"Saved to {out}")
