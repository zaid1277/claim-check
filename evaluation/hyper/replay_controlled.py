"""Fast in-process replay of the 175 controlled investigations (now
development evidence, per the hyper pass instructions) against the CURRENT
code, for calibration iteration. Not a substitute for the eventual new
held-out run -- this never touches evaluation/final/ or any lock.

No browser, no API process, no Postgres: calls app.services.pipeline.check_claim
directly with the same controlled fixture documents/sources application.py
uses, so a full iteration takes seconds, not minutes.
"""

import html
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "api"))

from app.core.errors import ProviderError  # noqa: E402
from app.core.settings import Settings  # noqa: E402
from app.services import article_extraction, pipeline, search  # noqa: E402
from app.services.embeddings import LocalEmbeddings  # noqa: E402
from app.services.nli import LocalNLI  # noqa: E402

ROWS = json.loads((REPO / "evaluation/final/data/verdicts.json").read_text())


def document(text):
    paragraphs = "".join(f"<p>{html.escape(p)}</p>" for p in text.split("\n"))
    return (
        f"<html><head><title>doc</title></head>"
        f"<body><article>{paragraphs}</article></body></html>"
    )


def run(rows=ROWS, settings=None):
    settings = settings or Settings(_env_file=None)
    settings.provider_mode = "live"
    embeddings = LocalEmbeddings(settings.embedding_model)
    nli = LocalNLI(settings.nli_model, settings.min_nli_confidence)
    results = []
    for row in rows:
        current = row

        def fetch(url, current=current):
            for source in current["sources"]:
                if url == source["url"]:
                    text = source["passage"]
                    if len(text) < 50:
                        text += (
                            " This is the statement contained in the supplied source."
                        )
                    return document(text), url
            raise ProviderError("not found")

        def make_search(configuration, current=current):
            provider = search.FixtureSearch(
                [
                    search.SearchResult(s["url"], "Controlled source")
                    for s in current["sources"]
                ]
            )
            return provider

        original_fetch = article_extraction.fetch_html
        original_search = search.make_search
        article_extraction.fetch_html = fetch
        search.make_search = make_search
        try:
            assessment = pipeline.check_claim(
                row["claim"], settings, search.make_search(settings), embeddings, nli
            )
        finally:
            article_extraction.fetch_html = original_fetch
            search.make_search = original_search
        results.append(
            {
                "id": row["id"],
                "expected": row["expected"],
                "predicted": assessment.verdict,
                "difficulty": row["difficulty"],
                "origin": row["origin"],
            }
        )
    return results


def summarize(results):
    n = len(results)
    correct = sum(1 for r in results if r["predicted"] == r["expected"])
    committed = [r for r in results if r["predicted"] != "INSUFFICIENT_EVIDENCE"]
    committed_correct = sum(1 for r in committed if r["predicted"] == r["expected"])
    false_abstentions = sum(
        1
        for r in results
        if r["predicted"] == "INSUFFICIENT_EVIDENCE"
        and r["expected"] != "INSUFFICIENT_EVIDENCE"
    )
    correct_abstentions = sum(
        1
        for r in results
        if r["predicted"] == "INSUFFICIENT_EVIDENCE"
        and r["expected"] == "INSUFFICIENT_EVIDENCE"
    )
    confident_errors = sum(
        1
        for r in results
        if r["predicted"] != "INSUFFICIENT_EVIDENCE" and r["predicted"] != r["expected"]
    )
    by_diff = {}
    for d in ["easy", "medium", "hard"]:
        rows = [r for r in results if r["difficulty"] == d]
        c = sum(1 for r in rows if r["predicted"] == r["expected"])
        by_diff[d] = {
            "n": len(rows),
            "correct": c,
            "accuracy": c / len(rows) if rows else None,
        }
    return {
        "n": n,
        "accuracy": correct / n,
        "coverage": len(committed) / n,
        "selective_accuracy": committed_correct / len(committed) if committed else None,
        "abstention_rate": (n - len(committed)) / n,
        "false_abstentions": false_abstentions,
        "correct_abstentions": correct_abstentions,
        "confident_errors": confident_errors,
        "by_difficulty": by_diff,
    }


if __name__ == "__main__":
    results = run()
    summary = summarize(results)
    print(json.dumps(summary, indent=2))
    out = Path(__file__).parent / "replay-results.json"
    out.write_text(json.dumps({"summary": summary, "rows": results}, indent=2))
    print(f"\nSaved to {out}")
