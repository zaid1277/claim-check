import os
from contextlib import contextmanager
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from app.db import migrate, reports
from app.services.investigation import DEMO_CLAIM, fixture_investigation


@pytest.mark.integration
def test_migrations_and_report_roundtrip(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration")
    schema = "test_" + uuid4().hex
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))

    @contextmanager
    def connect(settings):
        with psycopg.connect(url, options=f"-c search_path={schema}") as conn:
            yield conn

    monkeypatch.setattr(migrate, "get_connection", connect)
    monkeypatch.setattr(reports, "get_connection", connect)
    try:
        migrate.migrate()
        migrate.migrate()
        store = reports.PostgresReportStore()
        result = fixture_investigation(DEMO_CLAIM)
        from app.schemas.investigation import AtomicAssessment

        assessment = result.assessments[0]
        assessment.atomic_claims = [
            AtomicAssessment(
                claim=assessment.claim,
                verdict=assessment.verdict,
                support_total=assessment.support_total,
                contradict_total=0,
                evidence_indices=[0],
            )
        ]
        item = assessment.evidence[0]
        item.raw_stance = "contradict"
        item.stance = "neutral"
        item.counted = False
        item.exclusion_reason = "Different predicate."
        item.independence_group = "example.com"
        item.atomic_claim = assessment.claim
        store.save(result)
        assert store.get(str(result.id)) == result
        slug = store.publish(result.id)
        assert store.get(slug, shared=True).assessments == result.assessments
        assert store.publish(result.id) == slug
    finally:
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )
