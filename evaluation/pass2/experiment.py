"""Compare frozen corpora with cached inference; test requires --unlock-test."""

import argparse
import hashlib
import json
import resource
import time
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

import numpy as np
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

from app.core.settings import Settings
from app.services import pipeline
from app.services.article_extraction import Article
from app.services.embeddings import LocalEmbeddings
from app.services.nli import LocalNLI, interpret_label, load_nli
from app.services.retrieval import rank_passages
from app.services.search import FixtureSearch

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / ".cache"
CACHE.mkdir(exist_ok=True)


def key(claim, passage):
    return hashlib.sha256(json.dumps([claim, passage]).encode()).hexdigest()


def read(path):
    return json.loads(path.read_text()) if path.exists() else {}


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def metrics(rows, labels):
    truth = [r["expected"] for r in rows]
    pred = [r["predicted"] for r in rows]
    p, r, f, n = precision_recall_fscore_support(
        truth, pred, labels=labels, zero_division=0
    )
    result = dict(
        count=len(rows),
        accuracy=sum(a == b for a, b in zip(truth, pred, strict=True))
        / max(1, len(rows)),
        macro_f1=float(f.mean()),
        labels=labels,
        confusion_matrix=confusion_matrix(truth, pred, labels=labels).tolist(),
        per_label={
            label: dict(
                precision=float(p[i]),
                recall=float(r[i]),
                f1=float(f[i]),
                count=int(n[i]),
            )
            for i, label in enumerate(labels)
        },
    )
    if "contradict" in labels:
        negatives = [x for x in rows if x["expected"] != "contradict"]
        result["false_contradiction_rate"] = sum(
            x["predicted"] == "contradict" for x in negatives
        ) / max(1, len(negatives))
    else:
        decided = [x for x in rows if x["predicted"] != "INSUFFICIENT_EVIDENCE"]
        definitive = [x for x in rows if x["predicted"] in ["SUPPORTED", "UNSUPPORTED"]]
        result.update(
            decision_coverage=len(decided) / max(1, len(rows)),
            abstention_rate=1 - len(decided) / max(1, len(rows)),
            selective_accuracy=sum(x["predicted"] == x["expected"] for x in decided)
            / len(decided)
            if decided
            else None,
            incorrect_confident_verdict_rate=sum(
                x["predicted"] != x["expected"] for x in decided
            )
            / max(1, len(rows)),
            definitive_coverage=len(definitive) / max(1, len(rows)),
            definitive_accuracy=sum(x["predicted"] == x["expected"] for x in definitive)
            / len(definitive)
            if definitive
            else None,
        )
    return result


class CachedNLI:
    def __init__(self, model, temperature):
        self.model_name = model
        self.temperature = temperature
        self.path = CACHE / (model.replace("/", "--") + ".json")
        self.cache = read(self.path)
        self.local = LocalNLI(model, 0.65)
        self.labels = None

    def probabilities(self, claim, passage):
        k = key(claim, passage)
        if k not in self.cache:
            _, model = load_nli(self.model_name)
            captured = []

            def capture(module, inputs, output):
                captured.append(output.logits[0].detach().tolist())

            handle = model.register_forward_hook(capture)
            try:
                self.local.classify(claim, passage)
            finally:
                handle.remove()
            self.cache[k] = {
                "logits": captured[0],
                "labels": [
                    model.config.id2label[i].lower() for i in range(len(captured[0]))
                ],
            }
        row = self.cache[k]
        logits = np.array(row["logits"]) / self.temperature
        probs = np.exp(logits - logits.max())
        probs /= probs.sum()
        return dict(zip(row["labels"], map(float, probs), strict=True))

    def classify(self, claim, passage):
        probs = self.probabilities(claim, passage)
        label = max(probs, key=probs.get)
        return interpret_label(label, probs[label], 0.65)

    def save(self):
        write(self.path, self.cache)


class Reranker:
    def __init__(self):
        self.path = CACHE / "reranker.json"
        self.cache = read(self.path)
        self.model = None

    def score(self, claim, passage):
        k = key(claim, passage)
        if k not in self.cache:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            if self.model is None:
                name = "cross-encoder/ms-marco-MiniLM-L6-v2"
                self.tokenizer = AutoTokenizer.from_pretrained(name)
                self.model = AutoModelForSequenceClassification.from_pretrained(
                    name, attn_implementation="eager"
                ).double()
                self.model.eval()
            inputs = self.tokenizer(
                claim, passage, return_tensors="pt", truncation=True, max_length=512
            )
            with torch.inference_mode():
                self.cache[k] = float(self.model(**inputs).logits[0, 0])
        return self.cache[k]

    def save(self):
        write(self.path, self.cache)


class Embeddings:
    def __init__(self, name):
        self.path = CACHE / "embeddings.json"
        self.cache = read(self.path)
        self.local = LocalEmbeddings(name)

    def encode(self, texts):
        missing = list(dict.fromkeys(t for t in texts if t not in self.cache))
        if missing:
            self.cache.update(zip(missing, self.local.encode(missing), strict=True))
        return [self.cache[t] for t in texts]

    def save(self):
        write(self.path, self.cache)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", default="cross-encoder/nli-deberta-v3-small")
    p.add_argument("--output", required=True)
    p.add_argument(
        "--split",
        choices=["development", "validation", "test", "all"],
        default="validation",
    )
    p.add_argument("--unlock-test", action="store_true")
    p.add_argument("--seal-test", action="store_true")
    p.add_argument(
        "--policy", choices=["pass1", "semantic", "raw", "production"], default="pass1"
    )
    p.add_argument("--rerank", action="store_true")
    p.add_argument("--cutoff", type=float, default=0)
    p.add_argument("--temperature", type=float, default=1)
    p.add_argument("--nli-only", action="store_true")
    p.add_argument("--minimum-evidence", type=float, default=0.5)
    p.add_argument("--dominance-ratio", type=float, default=2)
    a = p.parse_args()
    if a.split in ["all", "test"] and not (a.unlock_test or a.seal_test):
        p.error(
            "Test needs --unlock-test after lock, or --seal-test for a blind baseline."
        )
    settings = Settings(
        _env_file=None,
        nli_model=a.model,
        minimum_evidence=a.minimum_evidence,
        dominance_ratio=a.dominance_ratio,
    )
    nli = CachedNLI(a.model, a.temperature)
    reranker = Reranker()
    embeddings = Embeddings(settings.embedding_model)
    original_gate = pipeline.gate_stance

    def gate(claim, passage, stance, confidence, published_at, settings):
        if a.policy == "pass1":
            import tarfile

            with tarfile.open(ROOT / "baseline/pass1-source.tar.gz") as archive:
                frozen = archive.extractfile("api/app/services/pipeline.py").read()
            if Path(pipeline.__file__).read_bytes() != frozen:
                raise ValueError(
                    "Run Pass 1 from its archived source, not the modified application."
                )
        if a.policy in ["pass1", "production"]:
            # gate_stance now returns 5 values (stance, exclusion, relevance
            # score, directness, relevance weight) as of the hyper pass's
            # graded-relevance work; this harness only ever consumed the
            # first two. Harness-only adaptation, not a reasoning change --
            # the same stance/reason values pipeline.gate_stance actually
            # computed are returned unchanged, just not the 3 extra fields
            # this experiment script never used.
            stance, exclusion, *_ = original_gate(
                claim, passage, stance, confidence, published_at, settings
            )
            return stance, exclusion
        reason = pipeline.temporal_exclusion(claim, published_at, settings)
        if a.policy == "semantic":
            reason = reason or pipeline.context_exclusion(claim, passage)
        if a.policy == "semantic" and reranker.score(claim, passage) < a.cutoff:
            reason = (
                "The relevance model does not find sufficient proposition relevance."
            )
        if (
            stance == "contradict"
            and confidence < settings.min_contradiction_confidence
        ):
            reason = "Contradiction confidence is below the required operating point."
        return ("neutral" if reason else stance), reason

    def rank(claim, passages, provider, top_k, min_similarity):
        ranked = rank_passages(
            claim, passages, provider, 20 if a.rerank else top_k, min_similarity
        )
        if a.rerank:
            ranked = sorted(
                ranked, key=lambda x: -reranker.score(claim, passages[x.index])
            )
        return ranked[:top_k]

    report = {"configuration": vars(a), "metrics": {}, "predictions": {}}
    with (
        patch.object(pipeline, "gate_stance", gate),
        patch.object(pipeline, "rank_passages", rank),
    ):
        for task in ["nli"] if a.nli_only else ["nli", "retrieval", "verdicts"]:
            rows = read(ROOT / f"data/{task}.json")
            rows = [r for r in rows if a.split == "all" or r["split"] == a.split]
            outputs = []
            for row in rows:
                start = time.perf_counter()
                base = {k: row[k] for k in ["id", "split", "domain"]}
                base["difficulty"] = row.get("difficulty", "unassigned")
                base["tag"] = row.get("tag", "")
                base["claim"] = row["claim"]
                if task == "nli":
                    raw, confidence = nli.classify(row["claim"], row["passage"])
                    stance, reason = gate(
                        row["claim"],
                        row["passage"],
                        raw,
                        confidence,
                        row.get("published_at"),
                        settings,
                    )
                    result = dict(
                        expected=row["label"],
                        predicted=stance,
                        raw=raw,
                        confidence=confidence,
                        probabilities=nli.probabilities(row["claim"], row["passage"]),
                        reason=reason,
                        origin=row["origin"],
                    )
                elif task == "retrieval":
                    ranked = rank(
                        row["claim"],
                        row["passages"],
                        embeddings,
                        10,
                        settings.min_similarity,
                    )
                    found = [r.index for r in ranked]
                    relevant = set(row["relevant"])
                    result = dict(
                        indices=found,
                        recall5=len(set(found[:5]) & relevant) / len(relevant)
                        if relevant
                        else None,
                        recall10=len(set(found[:10]) & relevant) / len(relevant)
                        if relevant
                        else None,
                        precision5=len(set(found[:5]) & relevant)
                        / max(1, len(found[:5])),
                    )
                else:
                    candidates = [
                        (
                            Article(
                                s["url"],
                                "Controlled authored evidence",
                                urlsplit(s["url"]).hostname,
                                s["passage"],
                                s["published_at"],
                            ),
                            s["passage"],
                        )
                        for s in row["sources"]
                    ]
                    with patch.object(
                        pipeline, "collect_evidence", return_value=candidates
                    ):
                        result = pipeline.check_claim(
                            row["claim"], settings, FixtureSearch([]), embeddings, nli
                        )
                    result = dict(
                        expected=row["expected"],
                        predicted=result.verdict,
                        assessment=result.model_dump(),
                    )
                outputs.append(
                    dict(base, **result, seconds=time.perf_counter() - start)
                )
            report["predictions"][task] = outputs
            report["metrics"][task] = {}
            for split in ["development", "validation", "test"]:
                subset = [r for r in outputs if r["split"] == split]
                if not subset:
                    continue
                if task == "retrieval":
                    summary = {
                        k: sum(r[k] for r in subset if r[k] is not None)
                        / max(1, sum(r[k] is not None for r in subset))
                        for k in ["recall5", "recall10", "precision5"]
                    }
                else:
                    labels = (
                        ["support", "contradict", "neutral"]
                        if task == "nli"
                        else [
                            "SUPPORTED",
                            "UNSUPPORTED",
                            "MIXED_EVIDENCE",
                            "INSUFFICIENT_EVIDENCE",
                        ]
                    )
                    summary = metrics(subset, labels)
                    if task == "nli":
                        summary["raw"] = metrics(
                            [dict(r, predicted=r["raw"]) for r in subset], labels
                        )
                        summary["by_origin"] = {
                            origin: metrics(
                                [r for r in subset if r["origin"] == origin], labels
                            )
                            for origin in ["authored", "ANLI"]
                        }
                    else:
                        summary["by_difficulty"] = {
                            d: metrics(
                                [r for r in subset if r["difficulty"] == d], labels
                            )
                            for d in ["easy", "medium", "hard"]
                        }
                summary["mean_seconds_cached"] = sum(
                    r["seconds"] for r in subset
                ) / len(subset)
                report["metrics"][task][split] = summary
                if split != "test" or not a.seal_test:
                    print(task, split, json.dumps(summary), flush=True)
            nli.save()
            reranker.save()
            embeddings.save()
            write(Path(a.output), report)
    report["peak_rss"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    write(Path(a.output), report)


if __name__ == "__main__":
    main()
