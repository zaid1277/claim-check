"""Accuracy-max pass, Phase 7 (diagnostic): does a second NLI model recover
signal the primary model misses on the passages behind actual errors?

Diagnostic-only, using the two prior holdouts' recorded error evidence
(never used to pick a final threshold). For every evidence item behind an
incorrect investigation, classify with a second model and compare its raw
label to what would have been the gold-correct stance for that piece of
evidence (inferred from whether the investigation's expected verdict is
SUPPORTED/UNSUPPORTED and the item's role, using the already-known
raw_stance of the primary model as one reference point).
"""

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "api"))
ROOT = Path(__file__).resolve().parent

import torch  # noqa: E402
from transformers import AutoModelForSequenceClassification, AutoTokenizer  # noqa: E402

from app.services.nli import normalize_hypothesis  # noqa: E402

SECOND_MODEL = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"


def load_error_evidence():
    errors_taxonomy = json.loads((ROOT / "results/error-taxonomy.json").read_text())
    by_id = {(r["source"], r["id"]): r for r in errors_taxonomy}
    rows = []
    for path, source in [
        (
            REPO / "evaluation/hyper/final/results/investigation-errors.json",
            "hyper-holdout",
        ),
        (
            REPO / "evaluation/remediation/final/results/investigation-errors.json",
            "remediation-confirmation",
        ),
    ]:
        for inv in json.loads(path.read_text()):
            meta = by_id.get((source, inv["id"]))
            if not meta:
                continue
            for e in inv["evidence"]:
                rows.append(
                    {
                        "investigation_id": inv["id"],
                        "source": source,
                        "expected_verdict": inv["expected"],
                        "predicted_verdict": inv["predicted"],
                        "error_category": meta["category"],
                        "claim": e["atomic_claim"],
                        "passage": e["passage"],
                        "primary_raw_stance": e["raw_stance"],
                        "primary_confidence": e["stance_confidence"],
                    }
                )
    return rows


def classify_second_model(rows):
    tokenizer = AutoTokenizer.from_pretrained(SECOND_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(SECOND_MODEL)
    model.eval()
    mapped = {
        "entailment": "support",
        "contradiction": "contradict",
        "neutral": "neutral",
    }
    id2label = model.config.id2label
    start = time.perf_counter()
    for r in rows:
        inputs = tokenizer(
            r["passage"],
            normalize_hypothesis(r["claim"]),
            return_tensors="pt",
            truncation="only_first",
            max_length=512,
        )
        with torch.inference_mode():
            probs = model(**inputs).logits[0].softmax(dim=-1)
        index = int(probs.argmax())
        r["secondary_raw_stance"] = mapped.get(id2label[index].lower())
        r["secondary_confidence"] = float(probs[index])
    print(f"Classified {len(rows)} pairs in {time.perf_counter() - start:.1f}s")
    return rows


def main():
    rows = load_error_evidence()
    n_investigations = len({r["investigation_id"] for r in rows})
    print(
        f"Loaded {len(rows)} evidence items behind {n_investigations} "
        "incorrect investigations"
    )
    rows = classify_second_model(rows)

    # Where the primary model's raw stance was neutral (the dominant
    # failure mode per the error taxonomy), does the secondary model
    # recognize a directional (support/contradict) stance that matches
    # the direction implied by the investigation's expected verdict?
    needed_direction = {"SUPPORTED": "support", "UNSUPPORTED": "contradict"}
    recovered = 0
    primary_neutral_relevant = 0
    for r in rows:
        want = needed_direction.get(r["expected_verdict"])
        if not want or r["primary_raw_stance"] != "neutral":
            continue
        primary_neutral_relevant += 1
        if r["secondary_raw_stance"] == want and r["secondary_confidence"] >= 0.65:
            recovered += 1

    print(
        f"\nOf {primary_neutral_relevant} evidence items where the PRIMARY model's "
        f"raw stance was neutral (on a claim expecting {list(needed_direction)}):"
    )
    print(
        f"  Secondary model (base) recovers the correct direction, confidently: "
        f"{recovered} ({100 * recovered / primary_neutral_relevant:.1f}%)"
        if primary_neutral_relevant
        else "  n/a"
    )

    (ROOT / "results/ensemble-complementarity.json").write_text(
        json.dumps(rows, indent=2)
    )
    print(f"\nWrote {len(rows)} rows to results/ensemble-complementarity.json")


if __name__ == "__main__":
    main()
