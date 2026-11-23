"""Real NLI and PostgreSQL; fixed retrieval avoids paid, changing web results."""

import os
from contextlib import contextmanager
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql

from app.core.settings import get_settings
from app.db import migrate, reports
from app.main import app
from app.services import article_extraction, embeddings, nli, pipeline, search

PARIS_PASSAGE = (
    "The Eiffel Tower is a wrought-iron lattice tower "
    "on the Champ de Mars in Paris, France."
)
LIVE_PASSAGE = (
    PARIS_PASSAGE
    + " It is named after the engineer Gustave Eiffel, whose company designed "
    "and built "
    'the tower from 1887 to 1889. Locally nicknamed "La dame de fer", it was '
    "constructed as the centerpiece of the 1889 World's Fair, and to crown the "
    "centennial anniversary of the French Revolution. Less"
)


@pytest.mark.integration
@pytest.mark.parametrize(
    "claim", ["The Eiffel Tower is in Paris.", "The Eiffel Tower is in Paris"]
)
@pytest.mark.parametrize(
    "passage", [PARIS_PASSAGE, LIVE_PASSAGE], ids=["sentence", "live-passage"]
)
def test_live_nli_stance_through_api_and_postgres(monkeypatch, claim, passage):
    url = os.getenv("TEST_DATABASE_URL")
    if not url or os.getenv("RUN_LOCAL_NLI_TESTS") != "1":
        pytest.skip("Requires TEST_DATABASE_URL and RUN_LOCAL_NLI_TESTS=1")

    schema = "test_nli_" + uuid4().hex
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))

    @contextmanager
    def connect(settings):
        with psycopg.connect(url, options=f"-c search_path={schema}") as conn:
            yield conn

    settings = get_settings()
    monkeypatch.setattr(settings, "provider_mode", "live")
    monkeypatch.setattr(migrate, "get_connection", connect)
    monkeypatch.setattr(reports, "get_connection", connect)
    store = reports.PostgresReportStore()
    app.dependency_overrides[reports.get_report_store] = lambda: store
    source = "https://example.gov/tower"
    monkeypatch.setattr(
        search,
        "make_search",
        lambda settings: search.FixtureSearch(
            [search.SearchResult(source, "Authored regression source")]
        ),
    )
    monkeypatch.setattr(
        article_extraction,
        "fetch_html",
        lambda url: (
            f"<html><body><article><p>{passage}</p></article></body></html>",
            url,
        ),
    )
    # Perfect relevance isolates stance propagation with the existing official weight.
    monkeypatch.setattr(
        embeddings.LocalEmbeddings,
        "encode",
        lambda self, texts: [[1, 0] for _ in texts],
    )

    _, model = nli.load_nli(settings.nli_model)
    raw_labels = []
    hook = model.register_forward_hook(
        lambda module, inputs, output: raw_labels.append(
            model.config.id2label[int(output.logits[0].argmax())].lower()
        )
    )
    classified = []
    original_classify = nli.LocalNLI.classify

    def classify(self, hypothesis, premise):
        assert (hypothesis, premise) == (claim, passage)
        result = original_classify(self, hypothesis, premise)
        classified.append(result[0])
        return result

    monkeypatch.setattr(nli.LocalNLI, "classify", classify)
    original_assess = pipeline.assess

    def assess(hypothesis, evidence, settings):
        assert all(item.stance == "support" for item in evidence)
        result = original_assess(hypothesis, evidence, settings)
        assert all(item.stance == "support" for item in result.evidence)
        return result

    monkeypatch.setattr(pipeline, "assess", assess)
    try:
        migrate.migrate()
        with TestClient(app) as client:
            response = client.post("/api/v1/investigations", json={"claims": [claim]})
            assert response.status_code == 200
            result = response.json()
            assert raw_labels == ["entailment"]
            assert classified == ["support"]
            assessment = result["assessments"][0]
            assert assessment["claim"] == claim
            assert assessment["verdict"] == "SUPPORTED"
            assert assessment["evidence"][0]["stance"] == "support"
            with connect(settings) as conn:
                assert conn.execute("SELECT stance FROM evidence").fetchall() == [
                    ("support",)
                ]
            restored = client.get(f"/api/v1/investigations/{result['id']}")
            assert restored.status_code == 200
            assert restored.json()["assessments"] == result["assessments"]
    finally:
        hook.remove()
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )
