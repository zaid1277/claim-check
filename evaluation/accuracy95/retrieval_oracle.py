"""Accuracy95 pass, Phase 2: a genuine retrieval-oracle benchmark using
REAL live search (not fixture evidence) -- the accuracy-max pass
explicitly could not measure this because every controlled investigation
uses fixture-injected evidence (retrieval succeeds by construction there).

For each of 30 new, independently-verified claims: run the real
`collect_evidence` pipeline against live search, embed and rank every
collected passage by similarity to the claim (the same ranking the
production pipeline uses), then check whether a passage carrying the
CORRECT-DIRECTION raw NLI stance appears in the top 5/10/20/50 -- Recall@K
in the retrieval-literature sense: was the needed information present
in the candidate pool at all, independent of what gating/aggregation
later does with it.
"""

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "api"))
ROOT = Path(__file__).resolve().parent

from app.core.settings import get_settings  # noqa: E402
from app.services.collection import collect_evidence  # noqa: E402
from app.services.embeddings import LocalEmbeddings  # noqa: E402
from app.services.nli import LocalNLI  # noqa: E402
from app.services.retrieval import rank_passages  # noqa: E402
from app.services.search import make_search  # noqa: E402

settings = get_settings()
settings.provider_mode = "live"
NEEDED_DIRECTION = {"SUPPORTED": "support", "UNSUPPORTED": "contradict"}


def load_claims():
    lines = (ROOT / "data/retrieval-oracle-claims.tsv").read_text().splitlines()[1:]
    return [
        dict(zip(["difficulty", "expected", "claim"], line.split("\t"), strict=True))
        for line in lines
        if line.strip()
    ]


def main():
    claims = load_claims()
    print(f"Loaded {len(claims)} claims for retrieval-oracle testing")

    embeddings = LocalEmbeddings(settings.embedding_model)
    nli = LocalNLI(
        settings.nli_model, 0.0
    )  # confidence=0 -- we want the RAW top label always, gating done manually below
    search = make_search(settings)

    results = []
    for i, row in enumerate(claims):
        claim = row["claim"]
        want = NEEDED_DIRECTION.get(row["expected"])
        start = time.perf_counter()
        try:
            candidates = collect_evidence(
                claim, search, max_sources=15, passage_words=100, max_passages=80
            )
        except Exception as exc:
            print(f"[{i}] FAILED to collect evidence for {claim!r}: {exc}")
            results.append(
                {"claim": claim, "difficulty": row["difficulty"], "error": str(exc)}
            )
            continue
        if not candidates:
            print(f"[{i}] no candidates at all for {claim!r}")
            results.append(
                {
                    "claim": claim,
                    "difficulty": row["difficulty"],
                    "n_candidates": 0,
                    "found_at_rank": None,
                }
            )
            continue
        texts = [text for _, text in candidates]
        ranked = rank_passages(
            claim, texts, embeddings, top_k=len(texts), min_similarity=-1.0
        )
        found_at_rank = None
        stances = []
        for rank, match in enumerate(ranked, start=1):
            _, passage = candidates[match.index]
            stance, confidence = nli.classify(claim, passage)
            stances.append({"rank": rank, "stance": stance, "confidence": confidence})
            if found_at_rank is None and stance == want and confidence >= 0.5:
                found_at_rank = rank
        elapsed = time.perf_counter() - start
        print(
            f"[{i}] {row['difficulty']:>6} n_candidates={len(candidates):>3} "
            f"found_at_rank={found_at_rank} ({elapsed:.1f}s): {claim[:60]}"
        )
        results.append(
            {
                "claim": claim,
                "difficulty": row["difficulty"],
                "expected": row["expected"],
                "n_candidates": len(candidates),
                "found_at_rank": found_at_rank,
                "top_stances": stances[:10],
                "elapsed_seconds": elapsed,
            }
        )

    valid = [r for r in results if "error" not in r]
    for k in [5, 10, 20, 50]:
        recall = sum(
            1
            for r in valid
            if r["found_at_rank"] is not None and r["found_at_rank"] <= k
        ) / len(valid)
        print(f"Recall@{k}: {recall:.3%}")

    (ROOT / "results/retrieval-oracle.json").write_text(json.dumps(results, indent=2))
    print(f"\nWrote {len(results)} results to results/retrieval-oracle.json")


if __name__ == "__main__":
    main()
