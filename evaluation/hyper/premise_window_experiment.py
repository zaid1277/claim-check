"""Group 3, phase 4: full passage vs. best-sentence-window premise, on the
120-pair validation split, using the winning NLI model. Validation only.
"""

import json
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "api"))

import torch  # noqa: E402
from transformers import AutoModelForSequenceClassification, AutoTokenizer  # noqa: E402

MODEL = "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli"
VALIDATION = [
    r
    for r in json.loads((REPO / "evaluation/final/data/nli.json").read_text())
    if r["split"] == "validation"
]
GATE = 0.70  # the chosen production contradiction gate; uniform here for comparability


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def content_words(text):
    return set(re.findall(r"\w+", text.lower()))


def best_window(claim, passage, radius=1):
    """The sentence with the highest claim word-overlap, plus `radius`
    sentences on either side -- a cheap, deterministic proxy for 'the
    sentence containing the highest proposition relevance' since re-running
    the real cross-encoder here would duplicate that model's own work."""
    sents = sentences(passage)
    if len(sents) <= (2 * radius + 1):
        return passage
    claim_words = content_words(claim)
    scores = [len(claim_words & content_words(s)) for s in sents]
    best = max(range(len(sents)), key=lambda i: scores[i])
    lo, hi = max(0, best - radius), min(len(sents), best + radius + 1)
    return " ".join(sents[lo:hi])


def normalize_hypothesis(claim):
    text = claim.strip()
    if text and not text.rstrip("\"'”’)]}").endswith((".", "!", "?", "…")):
        text += "."
    return text


def classify(tokenizer, model, id2label, passage, claim):
    inputs = tokenizer(
        passage,
        normalize_hypothesis(claim),
        return_tensors="pt",
        truncation="only_first",
        max_length=512,
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
    return gated, elapsed


def prf(rows, label):
    tp = sum(1 for r in rows if r["predicted"] == label and r["expected"] == label)
    fp = sum(1 for r in rows if r["predicted"] == label and r["expected"] != label)
    fn = sum(1 for r in rows if r["predicted"] != label and r["expected"] == label)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def macro_f1(rows):
    return (
        sum(prf(rows, label)[2] for label in ["support", "contradict", "neutral"]) / 3
    )


if __name__ == "__main__":
    tokenizer = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL)
    model.eval()
    id2label = model.config.id2label

    full_rows, window_rows = [], []
    full_latencies, window_latencies = [], []
    for r in VALIDATION:
        pred_full, t_full = classify(
            tokenizer, model, id2label, r["passage"], r["claim"]
        )
        full_latencies.append(t_full)
        full_rows.append({"expected": r["label"], "predicted": pred_full})

        windowed = best_window(r["claim"], r["passage"])
        pred_window, t_window = classify(
            tokenizer, model, id2label, windowed, r["claim"]
        )
        window_latencies.append(t_window)
        window_rows.append({"expected": r["label"], "predicted": pred_window})

    result = {
        "full_passage": {
            "macro_f1": macro_f1(full_rows),
            "contradiction_precision_recall": prf(full_rows, "contradict")[:2],
            "latency_ms_median": round(
                sorted(full_latencies)[len(full_latencies) // 2] * 1000, 1
            ),
        },
        "best_window": {
            "macro_f1": macro_f1(window_rows),
            "contradiction_precision_recall": prf(window_rows, "contradict")[:2],
            "latency_ms_median": round(
                sorted(window_latencies)[len(window_latencies) // 2] * 1000, 1
            ),
        },
    }
    print(json.dumps(result, indent=2))
    Path(__file__).with_name("premise-window-results.json").write_text(
        json.dumps(result, indent=2)
    )
