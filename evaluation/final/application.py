"""Loopback-only evaluation harness. Never load this module in a deployed server.

Only search results and source downloads are controlled. Extraction, ranking, NLI,
scoring, API validation and PostgreSQL use the application implementations.
"""

import html
import json
import os
import resource
import tarfile
from pathlib import Path

from fastapi import HTTPException

from app.core.settings import get_settings
from app.db.migrate import migrate
from app.main import app
from app.services import article_extraction, pipeline, search

ROOT = Path(__file__).resolve().parent
stage = os.environ.get("EVALUATION_STAGE", "final")
if stage != "development" and not (ROOT / "lock.json").exists():
    raise RuntimeError("Product holdout execution requires the final lock.")
variant = os.environ.get("EVALUATION_VARIANT", "candidate")
if variant == "pass2":
    with tarfile.open(ROOT / "baseline/pass2-source.tar.gz") as archive:
        frozen = archive.extractfile("api/app/services/propositions.py").read()
    namespace = {"__name__": "frozen_propositions"}
    exec(compile(frozen, "pass2-snapshot/propositions.py", "exec"), namespace)
    pipeline.decompose_claim = namespace["decompose_claim"]
settings = get_settings()
if not settings.database_url or "claim_check_test" not in str(settings.database_url):
    raise RuntimeError("Evaluation requires the disposable claim_check_test database.")
settings.provider_mode = "live"
settings.requests_per_minute = 300
migrate()
data_file = (
    (ROOT.parent / "pass2/data/verdicts.json")
    if stage == "development"
    else ROOT / "data/verdicts.json"
)
rows = {
    r["id"]: r
    for r in json.loads(data_file.read_text())
    if stage != "development" or r["split"] == "development"
}
current = None
trace = {}
original_fetch = article_extraction.fetch_html
original_search = search.make_search


def document(text):
    paragraphs = "".join(f"<p>{html.escape(p)}</p>" for p in text.split("\n"))
    return (
        "<html><head><title>Controlled evaluation document</title></head>"
        f"<body><article>{paragraphs}</article></body></html>"
    )


def fetch(url):
    trace["fetch_attempts"] = trace.get("fetch_attempts", 0) + 1
    if current:
        if url == f"https://evaluation-input.org/{current['id']}":
            return document(
                current["claim"]
                + (
                    "\nThis article is supplied for a controlled evidence "
                    "evaluation.\nThe reader may select a factual proposal "
                    "for investigation."
                )
            ), url
        for source in current["sources"]:
            if url == source["url"]:
                # A short assertion still needs enough article prose for extraction.
                text = source["passage"]
                if len(text) < 50:
                    text += " This is the statement contained in the supplied source."
                return document(text), url
    try:
        return original_fetch(url)
    except Exception:
        trace["extraction_failures"] = trace.get("extraction_failures", 0) + 1
        raise


class RecordedSearch:
    def __init__(self, provider):
        self.provider = provider

    def search(self, query):
        trace.setdefault("queries", []).append(query)
        try:
            return self.provider.search(query)
        except Exception:
            trace["search_failures"] = trace.get("search_failures", 0) + 1
            raise


def make_search(configuration):
    provider = (
        search.FixtureSearch(
            [
                search.SearchResult(s["url"], s.get("title", "Controlled source"))
                for s in current["sources"]
            ]
        )
        if current
        else original_search(configuration)
    )
    return RecordedSearch(provider)


article_extraction.fetch_html = fetch
search.make_search = make_search


@app.post("/evaluation/select/{identifier}")
def select(identifier: str):
    global current, trace
    if identifier != "live" and identifier not in rows:
        raise HTTPException(404)
    current = rows.get(identifier)
    trace = {}
    return {"selected": identifier}


@app.get("/evaluation/trace")
def get_trace():
    return dict(
        trace,
        variant=variant,
        stage=stage,
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    )
