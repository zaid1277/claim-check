"""Loopback-only evaluation harness for the Group 4 Hyper holdout. Never
load this module in a deployed server.

Only search results and source downloads are controlled. Extraction,
ranking, NLI, scoring, API validation and PostgreSQL use the application
implementations, exactly as the frozen Group 1-3 system ships them. Unlike
evaluation/final's harness, there is only one variant here -- the single
frozen system under evaluation/hyper/final/lock.json -- since Group 4 is not
comparing two systems, only holding the current one out on unseen data.
"""

import html
import json
import resource
from pathlib import Path

from fastapi import HTTPException

from app.core.settings import get_settings
from app.db.migrate import migrate
from app.main import app
from app.services import article_extraction, search

ROOT = Path(__file__).resolve().parent
if not (ROOT / "lock.json").exists():
    raise RuntimeError("Product holdout execution requires the hyper-final lock.")
settings = get_settings()
if not settings.database_url or "claim_check_test" not in str(settings.database_url):
    raise RuntimeError("Evaluation requires the disposable claim_check_test database.")
settings.provider_mode = "live"
settings.requests_per_minute = 300
migrate()
data_file = ROOT / "data/investigations.json"
rows = {r["id"]: r for r in json.loads(data_file.read_text())}
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
        if url == f"https://hyper-evaluation-input.org/{current['id']}":
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
        variant="hyper-final",
        stage="hyper",
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    )
