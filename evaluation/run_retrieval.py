"""Run from the repository root using the API virtual environment."""

import json
from datetime import UTC, datetime
from pathlib import Path

from app.core.settings import Settings
from app.services.embeddings import LocalEmbeddings
from app.services.retrieval import rank_passages

root = Path(__file__).resolve().parent
settings = Settings()
provider = LocalEmbeddings(settings.embedding_model)
data = json.loads((root / "retrieval.json").read_text())
results = {}
for k in (5, 10):
    recalls = []
    for row in data:
        ranked = rank_passages(
            row["claim"], row["passages"], provider, k, settings.min_similarity
        )
        found = {item.index for item in ranked} & set(row["relevant"])
        recalls.append(len(found) / len(row["relevant"]))
    results[f"recall@{k}"] = sum(recalls) / len(recalls)
output = {
    "dataset": "authored development examples; not a held-out benchmark",
    "queries": len(data),
    "model": settings.embedding_model,
    "min_similarity": settings.min_similarity,
    "measured_at": datetime.now(UTC).isoformat(),
    "metrics": results,
}
(root / "results").mkdir(exist_ok=True)
(root / "results/retrieval.json").write_text(json.dumps(output, indent=2) + "\n")
print(json.dumps(output, indent=2))
