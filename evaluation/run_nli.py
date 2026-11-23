"""Measure classification on an authored development set, not a benchmark."""

import json
from datetime import UTC, datetime
from pathlib import Path

from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

from app.core.settings import Settings
from app.services.nli import LocalNLI

root = Path(__file__).resolve().parent
settings = Settings()
model = LocalNLI(settings.nli_model, settings.min_nli_confidence)
rows = json.loads((root / "nli.json").read_text())
truth = [r["label"] for r in rows]
predictions = [model.classify(r["claim"], r["passage"])[0] for r in rows]
labels = ["support", "contradict", "neutral"]
p, r, f, _ = precision_recall_fscore_support(
    truth, predictions, labels=labels, average="macro", zero_division=0
)
output = {
    "dataset": "authored development examples; not held out",
    "pairs": len(rows),
    "model": settings.nli_model,
    "min_confidence": settings.min_nli_confidence,
    "measured_at": datetime.now(UTC).isoformat(),
    "macro_precision": float(p),
    "macro_recall": float(r),
    "macro_f1": float(f),
    "labels": labels,
    "confusion_matrix_rows_true_columns_predicted": confusion_matrix(
        truth, predictions, labels=labels
    ).tolist(),
    "predictions": predictions,
}
(root / "results").mkdir(exist_ok=True)
(root / "results/nli.json").write_text(json.dumps(output, indent=2) + "\n")
print(json.dumps(output, indent=2))
