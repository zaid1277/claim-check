"""NLI upgrade pass, Phases 12-13: full model evaluation on the NEW
validation split -- accuracy, macro F1, per-label P/R/F1, false
contradiction rate, opposite-direction error rate, scientific subset F1,
hard-negative-authored subset F1, latency, RAM. Works for the current
production model and any LoRA-adapted candidate, so both are measured
identically on the same held-out validation data.
"""

import argparse
import json
import resource
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "api"))
ROOT = Path(__file__).resolve().parent

import torch  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    confusion_matrix,
    precision_recall_fscore_support,
)
from transformers import AutoModelForSequenceClassification, AutoTokenizer  # noqa: E402

from app.services.nli import normalize_hypothesis  # noqa: E402

LABELS = ["support", "neutral", "contradict"]


def load_base(model_name):
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    model.eval()
    id2label = {int(k): v.lower() for k, v in model.config.id2label.items()}
    mapped = {
        "entailment": "support",
        "neutral": "neutral",
        "contradiction": "contradict",
    }
    id2label = {k: mapped[v] for k, v in id2label.items()}
    return tokenizer, model, id2label


def load_lora(adapter_dir):
    from peft import PeftModel

    config = json.loads((Path(adapter_dir) / "training-config.json").read_text())
    label2id = json.loads((Path(adapter_dir) / "label2id.json").read_text())
    id2label = {v: k for k, v in label2id.items()}
    tokenizer = AutoTokenizer.from_pretrained(adapter_dir)
    base = AutoModelForSequenceClassification.from_pretrained(
        "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
    )
    model = PeftModel.from_pretrained(base, adapter_dir)
    model.eval()
    return tokenizer, model, id2label, config.get("max_length", 384)


def classify_all(tokenizer, model, id2label, rows, max_length):
    n_params = sum(p.numel() for p in model.parameters())
    results = []
    total_time = 0.0
    with torch.inference_mode():
        for r in rows:
            inputs = tokenizer(
                r["passage"],
                normalize_hypothesis(r["claim"]),
                return_tensors="pt",
                truncation="only_first",
                max_length=max_length,
            )
            start = time.perf_counter()
            logits = model(**inputs).logits[0]
            elapsed = time.perf_counter() - start
            total_time += elapsed
            probs = logits.softmax(dim=-1)
            index = int(probs.argmax())
            results.append(
                {
                    "id": r["id"],
                    "expected": r["label"],
                    "predicted": id2label[index],
                    "confidence": float(probs[index]),
                    "origin": r.get("origin", "unknown"),
                    "tag": r.get("tag", "unknown"),
                }
            )
    peak_rss_mb = round(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024, 1
    )
    return results, {
        "n_params_millions": round(n_params / 1e6, 1),
        "peak_rss_mb": peak_rss_mb,
        "latency_ms_median": round(1000 * total_time / len(rows), 2) if rows else None,
    }


def summarize(results, label_filter=None, name="all"):
    rows = results if label_filter is None else [r for r in results if label_filter(r)]
    if not rows:
        return {"name": name, "n": 0}
    truth = [r["expected"] for r in rows]
    predicted = [r["predicted"] for r in rows]
    p, r_, f, n = precision_recall_fscore_support(
        truth, predicted, labels=LABELS, zero_division=0
    )
    accuracy = sum(a == b for a, b in zip(truth, predicted, strict=True)) / len(rows)
    macro_f1 = float(f.mean())
    cm = confusion_matrix(truth, predicted, labels=LABELS).tolist()
    negatives = sum(1 for t in truth if t != "contradict")
    false_contra = sum(
        1
        for t, p_ in zip(truth, predicted, strict=True)
        if t != "contradict" and p_ == "contradict"
    )
    opposite_contra_to_support = sum(
        1
        for t, p_ in zip(truth, predicted, strict=True)
        if t == "contradict" and p_ == "support"
    )
    opposite_support_to_contra = sum(
        1
        for t, p_ in zip(truth, predicted, strict=True)
        if t == "support" and p_ == "contradict"
    )
    return {
        "name": name,
        "n": len(rows),
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "per_label": {
            label: {
                "precision": float(p[i]),
                "recall": float(r_[i]),
                "f1": float(f[i]),
                "n": int(n[i]),
            }
            for i, label in enumerate(LABELS)
        },
        "confusion_matrix": cm,
        "false_contradiction_rate": false_contra / negatives if negatives else None,
        "opposite_direction": {
            "true_contradict_predicted_support": opposite_contra_to_support,
            "true_support_predicted_contradict": opposite_support_to_contra,
            "rate": (opposite_contra_to_support + opposite_support_to_contra)
            / len(rows),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model", required=True, help="HF model name, or a LoRA adapter dir if --lora"
    )
    parser.add_argument("--lora", action="store_true")
    parser.add_argument("--split", default="validation")
    parser.add_argument("--max-length", type=int, default=384)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    rows = json.loads((ROOT / f"data/{args.split}.json").read_text())
    print(f"Evaluating on {len(rows)} rows from data/{args.split}.json")

    if args.lora:
        tokenizer, model, id2label, max_length = load_lora(args.model)
    else:
        tokenizer, model, id2label = load_base(args.model)
        max_length = args.max_length

    results, meta = classify_all(tokenizer, model, id2label, rows, max_length)

    report = {
        "model": args.model,
        "meta": meta,
        "overall": summarize(results),
        "scientific_subset": summarize(
            results, lambda r: r["origin"] == "SciFact-train", "scientific"
        ),
        "hard_negative_subset": summarize(
            results, lambda r: r["tag"] == "hard-negative-authored", "hard-negative"
        ),
        "hard_contradiction_subset": summarize(
            results,
            lambda r: r["tag"] == "hard-contradiction-authored",
            "hard-contradiction",
        ),
        "results": results,
    }
    out_path = ROOT / "results" / args.out
    out_path.write_text(json.dumps(report, indent=2))
    overall = report["overall"]
    acc, f1 = overall["accuracy"], overall["macro_f1"]
    print(f"\nOverall: accuracy={acc:.3%} macro_f1={f1:.3%}")
    print(f"False contradiction rate: {overall['false_contradiction_rate']:.3%}")
    print(f"Opposite-direction rate: {overall['opposite_direction']['rate']:.3%}")
    sci_f1 = report["scientific_subset"].get("macro_f1", "n/a")
    print(f"Scientific subset macro F1: {sci_f1}")
    print(
        f"Latency (median ms): {meta['latency_ms_median']}  "
        f"Peak RSS (MB): {meta['peak_rss_mb']}"
    )
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
