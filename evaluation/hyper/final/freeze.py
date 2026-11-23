"""Freeze the Group-3 system before Hyper holdout construction/inference.

Adapted from evaluation/final/freeze.py -- same approach (hash source,
resolved configuration, model revisions, package versions), applied to the
current (Group 1-3) system state rather than the original Pass 2/candidate.
"""

import hashlib
import json
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from app.core.settings import get_settings

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    lock = ROOT / "lock.json"
    if lock.exists():
        raise SystemExit("A hyper-final lock already exists; do not overwrite it.")
    final_lock = "--final" in __import__("sys").argv
    checks = {
        "backend-tests.log": "167 passed",
        "frontend-tests.log": "13 passed",
        "extension-tests.log": "pass 2",
        "backend-lint.log": "All checks passed",
        "frontend-format.log": "All matched files use Prettier code style!",
        "playwright.log": "14 passed",
    }
    for filename, marker in checks.items():
        text = (ROOT.parent / "results" / filename).read_text()
        if marker not in text:
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
    ]:
        files += [
            p
            for p in (REPO / directory).rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
        ]
    if final_lock:
        # Phase 11: also freeze the new benchmark data and the harness that
        # runs it, so nothing in either can be edited between this lock and
        # the actual held-out run without being caught.
        files += [
            p
            for p in ROOT.rglob("*")
            if p.is_file()
            and "__pycache__" not in p.parts
            and ".cache" not in p.parts
            and p.parent != ROOT / "results"
            and p.name not in {"lock.json", "freeze.py"}
        ]
        # Shared pass2 harness infrastructure evaluation/hyper/final/run_pairs.py
        # imports and depends on -- a real bug in it (a stale 2-value gate_stance
        # unpack, fixed for the hyper pass) was found and fixed while wiring up
        # the final run; freezing it here too so it's protected going forward.
        files.append(REPO / "evaluation/pass2/experiment.py")
    files += [
        REPO / p
        for p in [
            "api/pyproject.toml",
            "web/package.json",
            "web/package-lock.json",
            "web/next.config.ts",
        ]
    ]
    configuration = get_settings().model_dump(
        mode="json",
        exclude={"database_url", "tavily_api_key", "brave_search_api_key"},
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
            "Preserve exactly the Group 1-3 system: graded proposition "
            "relevance, recalibrated source weights, capped same-domain "
            "duplicate discount, claim-risk caution tiers, max_sources=15, "
            "bounded follow-up retrieval, authority tiebreak, "
            "min_contradiction_confidence=0.70, minimum_evidence=0.20, "
            "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli. No "
            "further reasoning/model/threshold change after this lock "
            "except a documented, reasoning-neutral harness repair if the "
            "evaluation cannot otherwise execute."
        ),
        final_rule=(
            "One recorded attempt per product case; the NLI holdout and "
            "controlled investigations are checkpointed. No post-test "
            "reasoning edits."
        ),
    )
    lock.write_text(json.dumps(data, indent=2) + "\n")
    print("Hyper final lock:", digest(lock))


if __name__ == "__main__":
    main()
