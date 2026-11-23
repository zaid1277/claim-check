"""Remediation pass 5, Parts 2-5: run every candidate NLI model, and the
production relevance model, over the full 684-pair multi-fold corpus ONCE,
caching every raw score. All downstream fold analysis (threshold sweeps,
model comparison, two-signal gating) reads this cache instead of re-running
inference, so we can iterate on calibration logic freely without re-paying
model latency -- and, per Part 16, without ever touching the Hyper holdout.
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
from app.services.proposition_relevance import relevance_score  # noqa: E402
from app.services.temporal_scope import (  # noqa: E402
    context_exclusion,
    needs_current_evidence,
)

CANDIDATES = {
    "current": "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli",
    "previous-base": "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
    # facebook/bart-large-mnli (the originally intended third candidate) was
    # tried first and reproducibly crashed this machine's CPU inference with
    # SIGBUS (exit 138) on the very first batch -- a known class of
    # float32-CPU-inference instability on this hardware (the codebase
    # already carries an identical documented workaround for the smaller
    # proposition-relevance model, forced to float64/eager for the same
    # reason; bart-large-mnli was not similarly patchable without changing
    # a candidate-comparison script into production model-loading code).
    # cross-encoder/nli-deberta-v3-small substituted as a practical,
    # locally-available third candidate that runs cleanly.
    "alternative": "cross-encoder/nli-deberta-v3-small",
}

CORPUS = json.loads((ROOT / "data/contradiction-corpus.json").read_text())


def classify_all(model_name):
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    model.eval()
    id2label = model.config.id2label
    mapped = {
        "entailment": "support",
        "contradiction": "contradict",
        "neutral": "neutral",
    }
    rows = []
    for r in CORPUS:
        inputs = tokenizer(
            r["passage"],
            normalize_hypothesis(r["claim"]),
            return_tensors="pt",
            truncation="only_first",
            max_length=512,
        )
        start = time.perf_counter()
        with torch.inference_mode():
            probs = model(**inputs).logits[0].softmax(dim=-1)
        elapsed = time.perf_counter() - start
        index = int(probs.argmax())
        by_label = {}
        for i in range(probs.shape[0]):
            lbl = mapped.get(id2label[i].lower())
            if lbl:
                by_label[lbl] = float(probs[i])
        rows.append(
            {
                "id": r["id"],
                "raw": mapped.get(id2label[index].lower(), id2label[index].lower()),
                "confidence": float(probs[index]),
                "probabilities": by_label,
                "elapsed": elapsed,
            }
        )
    import resource

    peak_rss_mb = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    n_params = sum(p.numel() for p in model.parameters())
    return rows, peak_rss_mb, round(n_params / 1e6, 1)


def score_relevance_and_filters():
    rows = []
    for r in CORPUS:
        score = relevance_score(
            r["claim"], r["passage"], "cross-encoder/ms-marco-MiniLM-L6-v2"
        )
        exclusion = context_exclusion(r["claim"], r["passage"])
        if needs_current_evidence(r["claim"]):
            exclusion = exclusion or (
                "Currentness cannot be established without a usable publication date."
            )
        rows.append(
            {"id": r["id"], "relevance_score": score, "pre_nli_exclusion": exclusion}
        )
    return rows


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--relevance-only":
        rel = score_relevance_and_filters()
        (ROOT / "results/relevance-scores.json").write_text(json.dumps(rel, indent=2))
        print(f"Wrote {len(rel)} relevance scores")
        return
    key = sys.argv[1] if len(sys.argv) > 1 else None
    if key not in CANDIDATES:
        raise SystemExit(
            f"usage: score_corpus.py <{'|'.join(CANDIDATES)}|--relevance-only>"
        )
    print(f"Scoring {CANDIDATES[key]} ...", file=sys.stderr)
    rows, peak_rss_mb, n_params = classify_all(CANDIDATES[key])
    out = {
        "model_key": key,
        "model_name": CANDIDATES[key],
        "n_params_millions": n_params,
        "peak_rss_mb": peak_rss_mb,
        "rows": rows,
    }
    (ROOT / f"results/nli-scores-{key}.json").write_text(json.dumps(out, indent=2))
    print(f"Wrote {len(rows)} rows -> results/nli-scores-{key}.json")
    print(f"peak_rss_mb={peak_rss_mb} n_params_millions={n_params}")


if __name__ == "__main__":
    main()
