"""Controlled-corpus evaluation. No web calls; test metrics require --reveal-test."""

import argparse
import json
import resource
import time
from pathlib import Path
from unittest.mock import patch

from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

from app.core.settings import Settings
from app.services import pipeline
from app.services.article_extraction import Article
from app.services.embeddings import LocalEmbeddings
from app.services.nli import LocalNLI
from app.services.pipeline import check_claim
from app.services.retrieval import rank_passages
from app.services.search import FixtureSearch

ROOT = Path(__file__).resolve().parent


def metrics(truth, predicted, labels):
    p, r, f, n = precision_recall_fscore_support(
        truth, predicted, labels=labels, zero_division=0
    )
    return {
        "accuracy": sum(a == b for a, b in zip(truth, predicted, strict=True))
        / max(len(truth), 1),
        "macro_f1": float(f.mean()),
        "per_label": {
            label: {
                "precision": float(p[i]),
                "recall": float(r[i]),
                "f1": float(f[i]),
                "count": int(n[i]),
            }
            for i, label in enumerate(labels)
        },
        "labels": labels,
        "confusion_matrix": confusion_matrix(truth, predicted, labels=labels).tolist(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="typeform/distilbert-base-uncased-mnli")
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--split", choices=["all", "development", "validation", "test"], default="all"
    )
    parser.add_argument("--reveal-test", action="store_true")
    parser.add_argument("--nli-only", action="store_true")
    args = parser.parse_args()
    settings = Settings(_env_file=None, nli_model=args.model)
    nli = LocalNLI(settings.nli_model, settings.min_nli_confidence)
    embeddings = LocalEmbeddings(settings.embedding_model)
    report = {
        "model": args.model,
        "settings": settings.model_dump(
            mode="json",
            exclude={"database_url", "tavily_api_key", "brave_search_api_key"},
        ),
        "data_manifest": json.loads((ROOT / "data/manifest.json").read_text()),
        "metrics": {},
        "predictions": {},
    }
    for name in ["nli"] if args.nli_only else ["nli", "retrieval", "verdicts"]:
        data = json.loads((ROOT / f"data/{name}.json").read_text())
        if args.split != "all":
            data = [r for r in data if r["split"] == args.split]
        outputs = []
        for row in data:
            t = time.perf_counter()
            if name == "nli":
                predicted, confidence = nli.classify(row["claim"], row["passage"])
                gate_stance = getattr(pipeline, "gate_stance", None)
                gated, reason = (
                    gate_stance(
                        row["claim"],
                        row["passage"],
                        predicted,
                        confidence,
                        None,
                        settings,
                    )
                    if gate_stance
                    else (predicted, None)
                )
                result = {
                    "predicted": predicted,
                    "expected": row["label"],
                    "confidence": confidence,
                    "gated": gated,
                    "exclusion_reason": reason,
                }
            elif name == "retrieval":
                ranks = rank_passages(
                    row["claim"],
                    row["passages"],
                    embeddings,
                    10,
                    settings.min_similarity,
                )
                found = [r.index for r in ranks]
                relevant = set(row["relevant"])
                result = {
                    "indices": found,
                    "recall5": len(set(found[:5]) & relevant) / len(relevant),
                    "recall10": len(set(found[:10]) & relevant) / len(relevant),
                    "addressing5": len(set(found[:5]) & relevant)
                    / max(len(found[:5]), 1),
                }
            else:
                candidates = []
                for source in row["sources"]:
                    from urllib.parse import urlsplit

                    candidates.append(
                        (
                            Article(
                                source["url"],
                                "Authored controlled evidence",
                                urlsplit(source["url"]).hostname,
                                source["passage"],
                                source["published_at"],
                            ),
                            source["passage"],
                        )
                    )
                with patch(
                    "app.services.pipeline.collect_evidence", return_value=candidates
                ):
                    assessment = check_claim(
                        row["claim"], settings, FixtureSearch([]), embeddings, nli
                    )
                result = {
                    "predicted": assessment.verdict,
                    "expected": row["expected"],
                    "assessment": assessment.model_dump(),
                }
            outputs.append(
                dict(
                    result,
                    id=row["id"],
                    group=row["group"],
                    split=row["split"],
                    difficulty=row["difficulty"],
                    domain=row["domain"],
                    tag=row["tag"],
                    seconds=time.perf_counter() - t,
                )
            )
        report["predictions"][name] = outputs
        report["metrics"][name] = {}
        for split in ["development", "validation", "test"]:
            subset = [r for r in outputs if r["split"] == split]
            if not subset:
                continue
            if name == "retrieval":
                summary = {
                    key: sum(r[key] for r in subset) / len(subset)
                    for key in ["recall5", "recall10", "addressing5"]
                }
            else:
                labels = (
                    ["support", "contradict", "neutral"]
                    if name == "nli"
                    else [
                        "SUPPORTED",
                        "UNSUPPORTED",
                        "MIXED_EVIDENCE",
                        "INSUFFICIENT_EVIDENCE",
                    ]
                )
                summary = metrics(
                    [r["expected"] for r in subset],
                    [r["predicted"] for r in subset],
                    labels,
                )
                summary["by_difficulty"] = {
                    d: metrics(
                        [r["expected"] for r in subset if r["difficulty"] == d],
                        [r["predicted"] for r in subset if r["difficulty"] == d],
                        labels,
                    )["accuracy"]
                    for d in ["easy", "medium", "difficult"]
                }
                if name == "nli":
                    noncontra = [r for r in subset if r["expected"] != "contradict"]
                    summary["false_contradiction_rate"] = sum(
                        r["predicted"] == "contradict" for r in noncontra
                    ) / len(noncontra)
                    summary["gated"] = metrics(
                        [r["expected"] for r in subset],
                        [r["gated"] for r in subset],
                        labels,
                    )
                    summary["gated"]["false_contradiction_rate"] = sum(
                        r["gated"] == "contradict" for r in noncontra
                    ) / len(noncontra)
            summary["count"] = len(subset)
            summary["mean_seconds"] = sum(r["seconds"] for r in subset) / len(subset)
            report["metrics"][name][split] = summary
            if split != "test" or args.reveal_test:
                print(name, split, json.dumps(summary), flush=True)
    report["peak_process_rss_bytes"] = resource.getrusage(
        resource.RUSAGE_SELF
    ).ru_maxrss
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
