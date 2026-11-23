"""Accuracy-max pass, Phase 1: complete failure decomposition.

Reclassifies every incorrect investigation from BOTH the Group 4 Hyper
holdout and the remediation confirmation holdout into the fine-grained
A-S taxonomy, using the actual stored evidence records (raw NLI stance,
exclusion reasons, relevance scores, source weights, independence groups)
-- not just the coarse category the prior passes' summarize.py assigned.

Diagnostic-only: per the accuracy-max instructions, both holdouts are used
here only to find root causes, never to pick a final threshold.
"""

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CATEGORY_LABELS = {
    "A": "search/query failure",
    "B": "source not found",
    "C": "page extraction failure",
    "D": "relevant passage not retrieved/excluded pre-NLI",
    "E": "reranking failure",
    "F": "claim decomposition failure",
    "G": "NLI support miss",
    "H": "NLI contradiction miss",
    "I": "false contradiction",
    "J": "neutral misclassification (masks real signal)",
    "K": "temporal reasoning",
    "L": "numerical reasoning",
    "M": "entity mismatch",
    "N": "source-quality mistake",
    "O": "source-independence mistake",
    "P": "aggregation mistake",
    "Q": "false abstention",
    "R": "compound-claim policy",
    "S": "genuinely ambiguous / bad gold case",
}

NUMBER = re.compile(r"\d")
DATE_WORD = re.compile(r"\b(19|20)\d{2}\b|\b(current|now|today|latest)\b", re.I)


def classify(row):
    """Return (letter, note) for one incorrect investigation."""
    evidence = row["evidence"]
    expected, predicted = row["expected"], row["predicted"]
    claim = evidence[0]["atomic_claim"] if evidence else row.get("id", "")

    if not evidence:
        # Controlled fixtures with genuinely no sources are either a
        # designed empty-retrieval test (tag) or a construction gap.
        if row.get("tag") == "empty-retrieval" or "insufficient" in row.get("tag", ""):
            return "S", "designed empty-retrieval case; check gold label"
        return "B", "no evidence at all reached the pipeline"

    counted = [e for e in evidence if e["counted"]]
    raw_support = [e for e in evidence if e["raw_stance"] == "support"]
    raw_contradict = [e for e in evidence if e["raw_stance"] == "contradict"]

    # Entity-mismatch heuristic: excluded evidence whose passage shares
    # very little word overlap with the claim's named-entity-like tokens
    # (capitalized multi-word spans) -- a rough, inspectable signal, not a
    # real NER model.
    def entities(text):
        return set(re.findall(r"\b[A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)*\b", text))

    claim_entities = entities(claim)

    # 1. Everything filtered pre-NLI (all neutral, all excluded) --
    # distinguish temporal/entity/relevance/decomposition causes.
    if not counted:
        reasons = " ".join((e.get("exclusion_reason") or "") for e in evidence)
        if (
            "publication date" in reasons
            or "reporting period" in reasons
            or "product version" in reasons
        ):
            return "K", "temporal/context exclusion filtered all evidence"
        if "irrelevance floor" in reasons:
            # Was there real signal (raw support/contradict) among the
            # excluded-for-relevance items? If so this is a retrieval/
            # relevance-gate problem, not a genuine NLI miss.
            if raw_support or raw_contradict:
                passage_entities = set()
                for e in evidence:
                    passage_entities |= entities(e["passage"])
                if claim_entities and not (claim_entities & passage_entities):
                    return "M", "excluded evidence shares no named entities with claim"
                return (
                    "D",
                    "real raw support/contradict signal excluded by relevance floor",
                )
            return "D", "all evidence below relevance floor, no real signal present"
        if "confidence" in reasons:
            return (
                "H" if expected == "UNSUPPORTED" else "G",
                "raw contradict/support present but below confidence gate",
            )
        return "J", "all evidence genuinely neutral per raw NLI"

    # 2. Evidence was counted (real signal reached aggregation).
    independent = len({e["independence_group"] for e in counted})
    duplicate_discounted = [
        e for e in counted if "reduced weight" in (e.get("exclusion_reason") or "")
    ]

    if predicted == "INSUFFICIENT_EVIDENCE" and expected != "INSUFFICIENT_EVIDENCE":
        if duplicate_discounted:
            return (
                "O",
                "syndicated/duplicate-domain discount likely suppressed real weight",
            )
        return (
            "Q",
            "counted evidence existed but totals fell below the aggregation threshold",
        )

    if predicted == "MIXED_EVIDENCE" and expected in {"SUPPORTED", "UNSUPPORTED"}:
        if independent < 2:
            return (
                "N",
                "authority tiebreak did not fire despite a single dominant source",
            )
        return (
            "P",
            "genuine two-sided evidence; aggregation tiebreak did not resolve it",
        )

    if expected == "MIXED_EVIDENCE" and predicted != "MIXED_EVIDENCE":
        return "P", "one-sided aggregation total masked real disagreement"

    if predicted == "UNSUPPORTED" and expected == "SUPPORTED":
        # A contradiction won that shouldn't have.
        wrong_contradicts = [e for e in counted if e["stance"] == "contradict"]
        if wrong_contradicts:
            if any(
                DATE_WORD.search(claim) and DATE_WORD.search(e["passage"])
                for e in wrong_contradicts
            ):
                return (
                    "K",
                    "temporally-distinct evidence treated as a live contradiction",
                )
            if any(NUMBER.search(claim) for e in wrong_contradicts) and NUMBER.search(
                claim
            ):
                return (
                    "L",
                    "numeric evidence contradicted without aligned-unit comparison",
                )
            return "I", "false contradiction outweighed real support"
        return "P", "support present but outweighed by aggregation math"

    if predicted == "SUPPORTED" and expected == "UNSUPPORTED":
        missed = [
            e for e in raw_contradict if e not in counted or e["stance"] != "contradict"
        ]
        if missed:
            return "H", "raw contradiction present but not retained/counted"
        return "G", "no real contradiction signal reached aggregation at all"

    if predicted == "UNSUPPORTED" and expected == "MIXED_EVIDENCE":
        return "P", "real support evidence outweighed rather than mixed"

    if predicted == "SUPPORTED" and expected == "MIXED_EVIDENCE":
        return "H", "contradiction evidence not retained/counted"

    return "S", "does not match a clean root-cause pattern; needs manual review"


def run(path, source_label):
    rows = json.loads(Path(path).read_text())
    results = []
    for row in rows:
        letter, note = classify(row)
        results.append(
            {
                "source": source_label,
                "id": row["id"],
                "difficulty": row["difficulty"],
                "origin": row["origin"],
                "expected": row["expected"],
                "predicted": row["predicted"],
                "category": letter,
                "category_label": CATEGORY_LABELS[letter],
                "note": note,
            }
        )
    return results


def main():
    hyper = run(
        ROOT.parent / "hyper/final/results/investigation-errors.json", "hyper-holdout"
    )
    remediation = run(
        ROOT.parent / "remediation/final/results/investigation-errors.json",
        "remediation-confirmation",
    )
    combined = hyper + remediation
    (ROOT / "results/error-taxonomy.json").write_text(json.dumps(combined, indent=2))

    print(f"Total incorrect investigations analyzed: {len(combined)}")
    counts = Counter(r["category"] for r in combined)
    print("\nBy category (all sources combined):")
    for letter in CATEGORY_LABELS:
        n = counts.get(letter, 0)
        if n:
            pct = 100 * n / len(combined)
            print(f"  {letter} ({CATEGORY_LABELS[letter]}): {n} ({pct:.1f}%)")

    for source in ["hyper-holdout", "remediation-confirmation"]:
        subset = [r for r in combined if r["source"] == source]
        print(f"\n--- {source} ({len(subset)} errors) ---")
        c = Counter(r["category"] for r in subset)
        for letter, n in c.most_common():
            pct = 100 * n / len(subset)
            print(f"  {letter} ({CATEGORY_LABELS[letter]}): {n} ({pct:.1f}%)")

    print("\n--- hard-difficulty only ---")
    hard = [r for r in combined if r["difficulty"] == "hard"]
    c = Counter(r["category"] for r in hard)
    for letter, n in c.most_common():
        print(
            f"  {letter} ({CATEGORY_LABELS[letter]}): {n} ({100 * n / len(hard):.1f}%)"
        )


if __name__ == "__main__":
    main()
