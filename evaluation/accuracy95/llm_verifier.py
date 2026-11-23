"""Accuracy95 pass, Phase 7-8: evaluate a small, locally-run, instruction-
tuned LLM as an "evidence-grounded reasoning" verifier -- given ONLY the
claim and evidence, does the model produce SUPPORTED/CONTRADICTED/
INSUFFICIENT, reasoning strictly from the supplied text (Phase 7's exact
framing: "does this evidence establish, contradict, partially establish,
or fail to establish this claim", not "is this claim true").

Model: Qwen2.5-1.5B-Instruct, bfloat16, CPU inference. Free, local, no API
costs (per the user's explicit constraint). Evaluated on a representative
STRATIFIED SUBSET of the nli-upgrade validation split (120 of 380 pairs,
40/label) -- the full 380 would take over an hour at ~11s/pair; this
subset is large enough for a real macro-F1/precision/recall signal while
staying within this session's time budget. Explicitly disclosed as a
subset, not silently narrowed.
"""

import json
import re
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
NLI_UPGRADE = REPO / "evaluation/nli-upgrade"
ROOT = Path(__file__).resolve().parent

import torch  # noqa: E402
from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: E402

MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"

PROMPT_TEMPLATE = """You are a fact-verification assistant. Given a CLAIM \
and EVIDENCE, determine whether the evidence SUPPORTS, CONTRADICTS, or is \
INSUFFICIENT (NEUTRAL) to establish the claim. Reason ONLY from the \
supplied evidence text, not outside knowledge -- do not judge whether the \
claim is true in general, only whether THIS evidence establishes it.

CLAIM: {claim}
EVIDENCE: {evidence}

Respond with ONLY a JSON object in this exact format, nothing else:
{{"stance": "support" | "contradict" | "neutral", "confidence": 0.0-1.0, \
"reasoning": "brief explanation"}}"""


def load_subset(n_per_label=40):
    rows = json.loads((NLI_UPGRADE / "data/validation.json").read_text())
    by_label = {}
    for r in rows:
        by_label.setdefault(r["label"], []).append(r)
    subset = []
    for group in by_label.values():
        group = sorted(group, key=lambda r: r["id"])
        subset += group[:n_per_label]
    return subset


def classify(model, tokenizer, claim, evidence):
    prompt = PROMPT_TEMPLATE.format(claim=claim, evidence=evidence[:2000])
    messages = [{"role": "user", "content": prompt}]
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer([text], return_tensors="pt", truncation=True, max_length=1024)
    with torch.inference_mode():
        out = model.generate(
            **inputs,
            max_new_tokens=100,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    response = tokenizer.decode(
        out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True
    )
    match = re.search(r'\{[^{}]*"stance"[^{}]*\}', response, re.DOTALL)
    if not match:
        return None, None, response
    try:
        parsed = json.loads(match.group(0))
        stance = parsed.get("stance", "").lower()
        stance = {
            "support": "support",
            "contradict": "contradict",
            "neutral": "neutral",
        }.get(stance)
        confidence = float(parsed.get("confidence", 0.5))
        return stance, confidence, response
    except (json.JSONDecodeError, ValueError, TypeError):
        return None, None, response


def main():
    rows = load_subset()
    print(f"Evaluating LLM verifier on {len(rows)} pairs (stratified subset)")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, dtype=torch.bfloat16)
    model.eval()

    results = []
    start_all = time.perf_counter()
    for i, row in enumerate(rows):
        start = time.perf_counter()
        stance, confidence, raw = classify(
            model, tokenizer, row["claim"], row["passage"]
        )
        elapsed = time.perf_counter() - start
        results.append(
            {
                "id": row["id"],
                "expected": row["label"],
                "predicted": stance,
                "confidence": confidence,
                "origin": row.get("origin", "unknown"),
                "elapsed_seconds": elapsed,
                "raw_response": raw[:300],
            }
        )
        if (i + 1) % 10 == 0:
            done_elapsed = time.perf_counter() - start_all
            print(f"  {i + 1}/{len(rows)} done ({done_elapsed:.0f}s elapsed)")

    (ROOT / "results/llm-verifier-eval.json").write_text(json.dumps(results, indent=2))

    parse_failures = sum(1 for r in results if r["predicted"] is None)
    valid = [r for r in results if r["predicted"] is not None]
    correct = sum(1 for r in valid if r["predicted"] == r["expected"])
    print(f"\nParse failures: {parse_failures}/{len(results)}")
    print(
        f"Accuracy (of parsed): {correct}/{len(valid)} = {correct / len(valid):.3%}"
        if valid
        else "n/a"
    )

    from sklearn.metrics import f1_score, precision_recall_fscore_support

    labels = ["support", "neutral", "contradict"]
    truth = [r["expected"] for r in valid]
    pred = [r["predicted"] for r in valid]
    p, r_, f, n = precision_recall_fscore_support(
        truth, pred, labels=labels, zero_division=0
    )
    macro_f1 = f1_score(truth, pred, labels=labels, average="macro")
    print(f"Macro F1: {macro_f1:.3%}")
    for i, label in enumerate(labels):
        print(f"  {label}: P={p[i]:.3f} R={r_[i]:.3f} F1={f[i]:.3f} n={int(n[i])}")

    median_latency = sorted(r["elapsed_seconds"] for r in results)[len(results) // 2]
    print(f"Median latency: {median_latency:.2f}s")
    print(f"Total wall time: {time.perf_counter() - start_all:.0f}s")


if __name__ == "__main__":
    main()
