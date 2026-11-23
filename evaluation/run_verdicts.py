"""Evaluate the real local ML pipeline with authored, offline evidence passages."""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from app.core.settings import Settings
from app.services.article_extraction import Article
from app.services.embeddings import LocalEmbeddings
from app.services.nli import LocalNLI
from app.services.pipeline import check_claim
from app.services.search import FixtureSearch

root = Path(__file__).resolve().parent
settings = Settings()
embeddings = LocalEmbeddings(settings.embedding_model)
nli = LocalNLI(settings.nli_model, settings.min_nli_confidence)
rows = json.loads((root / "verdicts.json").read_text())
results = []
for row in rows:
    article = Article(
        "https://example.org/authored-fixture",
        "Authored evaluation passage",
        "example.org",
        "",
    )
    candidates = [(article, text) for text in row["passages"]]
    with patch("app.services.pipeline.collect_evidence", return_value=candidates):
        result = check_claim(row["claim"], settings, FixtureSearch([]), embeddings, nli)
    results.append({"expected": row["expected"], "result": result.model_dump()})
output = {
    "dataset": (
        "six authored offline cases; external retrieval mocked, "
        "real local embeddings and NLI"
    ),
    "measured_at": datetime.now(UTC).isoformat(),
    "correct": sum(item["expected"] == item["result"]["verdict"] for item in results),
    "cases": len(results),
    "results": results,
}
(root / "results").mkdir(exist_ok=True)
(root / "results/verdicts.json").write_text(json.dumps(output, indent=2) + "\n")
print(json.dumps({"correct": output["correct"], "cases": output["cases"]}))
