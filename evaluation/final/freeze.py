"""Freeze source, input corpora and resolved configuration before final inference."""

import hashlib
import json
import tarfile
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from app.core.settings import get_settings

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    lock = ROOT / "lock.json"
    if lock.exists():
        raise SystemExit("A final lock already exists; do not overwrite it.")
    # The final lock must follow engineering checks, not substitute for them.
    checks = {
        "backend-tests.log": "138 passed",
        "frontend-tests.log": "13 passed",
        "browser-release.log": "14 passed",
        "backend-lint.log": "All checks passed",
        "frontend-format.log": "All matched files use Prettier code style!",
    }
    for filename, marker in checks.items():
        if marker not in (ROOT / "results" / filename).read_text():
            raise SystemExit(f"Required successful check is missing: {filename}")
    files = []
    for directory in [
        "api/app",
        "api/tests",
        "api/migrations",
        "web/app",
        "web/components",
        "web/lib",
        "web/tests",
        "web/e2e",
        "extension",
        "evaluation/final/data",
    ]:
        files += [
            p
            for p in (REPO / directory).rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
        ]
    files += [
        REPO / p
        for p in [
            "api/pyproject.toml",
            "web/package.json",
            "web/package-lock.json",
            "web/next.config.ts",
        ]
    ]
    files += (
        list(ROOT.glob("*.py")) + list(ROOT.glob("*.mjs")) + list(ROOT.glob("*.sh"))
    )
    archive = ROOT / "candidate-source.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for path in sorted(set(files)):
            tar.add(path, arcname=str(path.relative_to(REPO)), recursive=False)
    configuration = get_settings().model_dump(
        mode="json", exclude={"database_url", "tavily_api_key", "brave_search_api_key"}
    )
    model_revisions = {}
    cache = Path.home() / ".cache/huggingface/hub"
    for key in ["nli_model", "embedding_model", "proposition_model"]:
        model = configuration[key]
        ref = cache / ("models--" + model.replace("/", "--")) / "refs/main"
        model_revisions[model] = (
            ref.read_text().strip() if ref.exists() else "Unavailable locally"
        )
    data = dict(
        created_at=datetime.now(UTC).isoformat(),
        archive_sha256=digest(archive),
        configuration=configuration,
        model_revisions=model_revisions,
        packages={
            p: version(p)
            for p in [
                "torch",
                "transformers",
                "sentence-transformers",
                "spacy",
                "trafilatura",
                "rapidocr-onnxruntime",
            ]
        },
        files={str(p.relative_to(REPO)): digest(p) for p in sorted(set(files))},
        decision=(
            "Keep all Pass 2 models, weights and thresholds. Only production "
            "change: preserve embedded/temporal attribution during decomposition."
        ),
        final_rule=(
            "One recorded attempt per product case; final pair inference is "
            "checkpointed. No post-test reasoning edits."
        ),
    )
    lock.write_text(json.dumps(data, indent=2) + "\n")
    print("Final lock:", digest(lock))


if __name__ == "__main__":
    main()
