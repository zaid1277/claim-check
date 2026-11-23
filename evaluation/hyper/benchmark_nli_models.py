"""Group 3, phase 1-3: NLI model comparison on the 120-pair validation split
(never the future Hyper holdout), plus recovery analysis against the 71
historical missed contradictions (development material, explicitly permitted
for before/after engineering comparison per the hyper-pass instructions).

Verifies label mapping per model (phase 3) rather than assuming index order.
"""

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "api"))

import torch  # noqa: E402
from transformers import AutoModelForSequenceClassification, AutoTokenizer  # noqa: E402

VALIDATION = [
    r
    for r in json.loads((REPO / "evaluation/final/data/nli.json").read_text())
    if r["split"] == "validation"
]
MISSED = json.loads(
    (REPO / "evaluation/hyper/missed-contradictions-pairs.json").read_text()
)
MISSED = [m for m in MISSED if m.get("passage")]

CANDIDATES = [
    "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",  # current production model
    "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli",
    "facebook/bart-large-mnli",
    "cross-encoder/nli-deberta-v3-small",
    "typeform/distilbert-base-uncased-mnli",
]

GATE = 0.65  # settings.min_nli_confidence, applied uniformly for comparability


def normalize_hypothesis(claim: str) -> str:
    text = claim.strip()
    if text and not text.rstrip("\"'”’)]}").endswith((".", "!", "?", "…")):
        text += "."
    return text


def classify(tokenizer, model, id2label, passage, claim, max_length=512):
    inputs = tokenizer(
        passage,
        normalize_hypothesis(claim),
        return_tensors="pt",
        truncation="only_first",
        max_length=max_length,
    )
    start = time.perf_counter()
    with torch.inference_mode():
        probs = model(**inputs).logits[0].softmax(dim=-1)
    elapsed = time.perf_counter() - start
    index = int(probs.argmax())
    confidence = float(probs[index])
    label = id2label[index].lower()
    mapped = {
        "entailment": "support",
        "contradiction": "contradict",
        "neutral": "neutral",
    }
    raw = mapped.get(label, label)
    gated = raw if confidence >= GATE else "neutral"
    return raw, gated, confidence, elapsed


def prf(rows, label):
    tp = sum(1 for r in rows if r["predicted"] == label and r["expected"] == label)
    fp = sum(1 for r in rows if r["predicted"] == label and r["expected"] != label)
    fn = sum(1 for r in rows if r["predicted"] != label and r["expected"] == label)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def evaluate(model_name):
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    model.eval()
    id2label = model.config.id2label
    n_params = sum(p.numel() for p in model.parameters())

    rows = []
    latencies = []
    for r in VALIDATION:
        raw, gated, conf, elapsed = classify(
            tokenizer, model, id2label, r["passage"], r["claim"]
        )
        latencies.append(elapsed)
        rows.append(
            {
                "id": r["id"],
                "expected": r["label"],
                "predicted": gated,
                "raw": raw,
                "confidence": conf,
            }
        )

    per_label = {
        label: prf(rows, label) for label in ["support", "contradict", "neutral"]
    }
    macro_f1 = sum(per_label[label]["f1"] for label in per_label) / 3
    accuracy = sum(1 for r in rows if r["predicted"] == r["expected"]) / len(rows)
    false_contradiction_rate = sum(
        1
        for r in rows
        if r["predicted"] == "contradict" and r["expected"] != "contradict"
    ) / sum(1 for r in rows if r["expected"] != "contradict")

    # Recovery analysis on the 71 historical missed contradictions.
    recovered_d = recovered_e = recovered_f = still_missed = 0
    for m in MISSED:
        _, gated, _, _ = classify(tokenizer, model, id2label, m["passage"], m["claim"])
        bucket = "D" if m["raw"] == "neutral" else "E" if m["raw"] == "support" else "F"
        if gated == "contradict":
            if bucket == "D":
                recovered_d += 1
            elif bucket == "E":
                recovered_e += 1
            else:
                recovered_f += 1
        else:
            still_missed += 1

    import resource

    peak_rss_mb = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)

    return {
        "model": model_name,
        "n_params_millions": round(n_params / 1e6, 1),
        "peak_rss_mb": peak_rss_mb,
        "id2label": dict(id2label),
        "macro_f1": macro_f1,
        "accuracy": accuracy,
        "per_label": per_label,
        "false_contradiction_rate": false_contradiction_rate,
        "latency_ms_median": round(sorted(latencies)[len(latencies) // 2] * 1000, 1),
        "latency_ms_p95": round(
            sorted(latencies)[int(0.95 * (len(latencies) - 1))] * 1000, 1
        ),
        "recovery": {
            "D_neutral_misses_recovered": f"{recovered_d}/32",
            "E_opposite_direction_recovered": f"{recovered_e}/27",
            "F_low_confidence_recovered": f"{recovered_f}/12",
            "still_missed": f"{still_missed}/71",
        },
        "validation_rows": rows,
    }


if __name__ == "__main__":
    # One model per invocation (`--model NAME`) so results can run in
    # separate processes for clean, isolated peak-RSS and to avoid CPU
    # oversubscription when run alongside other work; no arg runs all
    # candidates serially in this one process (rougher memory numbers).
    if len(sys.argv) > 1 and sys.argv[1] == "--model":
        name = sys.argv[2]
        result = evaluate(name)
        safe_name = name.replace("/", "__")
        out = Path(__file__).parent / f"nli-result-{safe_name}.json"
        out.write_text(json.dumps(result, indent=2))
        print(f"done {name} -> {out}")
    else:
        results = []
        for name in CANDIDATES:
            print(f"Evaluating {name}...", file=sys.stderr)
            try:
                result = evaluate(name)
                results.append(result)
                print(json.dumps(result, indent=2))
            except Exception as exc:
                print(f"FAILED {name}: {exc}", file=sys.stderr)
                results.append({"model": name, "error": str(exc)})
        out = Path(__file__).parent / "nli-model-comparison.json"
        out.write_text(json.dumps(results, indent=2))
        print(f"\nSaved to {out}")
