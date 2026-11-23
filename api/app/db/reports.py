import secrets
from collections import OrderedDict
from functools import lru_cache
from threading import Lock
from typing import Protocol
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.core.settings import get_settings
from app.db.connection import get_connection
from app.schemas.investigation import Assessment, Evidence, Investigation


class ReportStore(Protocol):
    def save(self, result: Investigation) -> None: ...
    def get(self, identifier: str, shared: bool = False) -> Investigation | None: ...
    def publish(self, identifier: UUID) -> str | None: ...


class MemoryReportStore:
    """Bounded, process-local fixture storage; never a persistence substitute."""

    def __init__(self):
        self.reports: OrderedDict[str, Investigation] = OrderedDict()
        self.lock = Lock()

    def save(self, result: Investigation) -> None:
        with self.lock:
            self.reports[str(result.id)] = result.model_copy(deep=True)
            if len(self.reports) > 100:
                self.reports.popitem(last=False)

    def get(self, identifier: str, shared: bool = False) -> Investigation | None:
        with self.lock:
            result = (
                next(
                    (r for r in self.reports.values() if r.share_slug == identifier),
                    None,
                )
                if shared
                else self.reports.get(identifier)
            )
            return result.model_copy(deep=True) if result else None

    def publish(self, identifier: UUID) -> str | None:
        with self.lock:
            result = self.reports.get(str(identifier))
            if result is None:
                return None
            if not result.share_slug:
                result.share_slug = secrets.token_urlsafe(18)
            return result.share_slug


class PostgresReportStore:
    def save(self, result: Investigation) -> None:
        with get_connection(get_settings()) as conn:
            conn.execute(
                """INSERT INTO investigations(id, input_type, raw_text,
source_url, status, created_at, mode) VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    result.id,
                    result.input_type,
                    result.raw_text,
                    result.source_url,
                    result.status,
                    result.created_at,
                    result.mode,
                ),
            )
            source_ids = {}
            for position, assessment in enumerate(result.assessments):
                claim_id = uuid4()
                conn.execute(
                    """INSERT INTO claims(id, investigation_id, claim_text,
position) VALUES (%s, %s, %s, %s)""",
                    (claim_id, result.id, assessment.claim, position),
                )
                for index, item in enumerate(assessment.evidence):
                    if item.url in source_ids:
                        source_id = source_ids[item.url]
                    else:
                        source_id = uuid4()
                        source_ids[item.url] = source_id
                        conn.execute(
                            "INSERT INTO sources VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                            (
                                source_id,
                                result.id,
                                item.url,
                                item.domain,
                                item.title,
                                item.published_at,
                                item.source_type,
                                item.source_weight,
                            ),
                        )
                    conn.execute(
                        "INSERT INTO evidence VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            uuid4(),
                            claim_id,
                            source_id,
                            item.passage,
                            item.similarity,
                            item.stance,
                            item.stance_confidence,
                            item.evidence_score,
                            index,
                            Jsonb(
                                item.model_dump(
                                    include={
                                        "raw_stance",
                                        "exclusion_reason",
                                        "independence_group",
                                        "counted",
                                        "atomic_claim",
                                        "relevance_score",
                                        "directness",
                                        "relevance_weight",
                                        "structured_signal",
                                    }
                                )
                            ),
                        ),
                    )
                conn.execute(
                    "INSERT INTO assessments VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        uuid4(),
                        claim_id,
                        assessment.support_total,
                        assessment.contradict_total,
                        assessment.verdict,
                        assessment.explanation,
                        Jsonb(result.model_metadata),
                        Jsonb([a.model_dump() for a in assessment.atomic_claims]),
                        assessment.verified_atom_fraction,
                        assessment.contradicted_atom_fraction,
                    ),
                )

    def get(self, identifier: str, shared: bool = False) -> Investigation | None:
        with (
            get_connection(get_settings()) as conn,
            conn.cursor(row_factory=dict_row) as cursor,
        ):
            # User values are parameterized; only fixed column choices are allowed.
            query = (
                "SELECT * FROM investigations WHERE share_slug=%s"
                if shared
                else "SELECT * FROM investigations WHERE id=%s"
            )
            row = cursor.execute(query, (identifier,)).fetchone()
            if row is None:
                return None
            claim_rows = cursor.execute(
                """SELECT c.claim_text, a.* FROM claims c JOIN
assessments a ON a.claim_id=c.id WHERE
c.investigation_id=%s ORDER BY c.position""",
                (row["id"],),
            ).fetchall()
            assessments = []
            for claim in claim_rows:
                evidence_rows = cursor.execute(
                    """SELECT s.title, s.url, s.domain, s.published_at,
s.source_type, s.source_weight, e.passage_text AS
passage, e.similarity, e.stance, e.stance_confidence,
e.evidence_score, e.analysis FROM evidence e JOIN sources s ON
s.id=e.source_id WHERE e.claim_id=%s ORDER BY
e.position""",
                    (claim["claim_id"],),
                ).fetchall()
                assessments.append(
                    Assessment(
                        claim=claim["claim_text"],
                        verdict=claim["verdict"],
                        explanation=claim["explanation"],
                        support_total=claim["support_total"],
                        contradict_total=claim["contradict_total"],
                        evidence=[
                            Evidence(
                                **{k: v for k, v in e.items() if k != "analysis"},
                                **e["analysis"],
                            )
                            for e in evidence_rows
                        ],
                        atomic_claims=claim["atomic_claims"],
                        verified_atom_fraction=claim["verified_atom_fraction"],
                        contradicted_atom_fraction=claim["contradicted_atom_fraction"],
                    )
                )
            return Investigation(
                id=row["id"],
                created_at=row["created_at"],
                mode=row["mode"],
                input_type=row["input_type"],
                source_url=row["source_url"],
                raw_text=row["raw_text"],
                share_slug=row["share_slug"],
                assessments=assessments,
                model_metadata=claim_rows[0]["model_metadata"] if claim_rows else {},
            )

    def publish(self, identifier: UUID) -> str | None:
        with get_connection(get_settings()) as conn:
            row = conn.execute(
                """UPDATE investigations SET share_slug=COALESCE(share_slug,
%s) WHERE id=%s RETURNING share_slug""",
                (secrets.token_urlsafe(18), identifier),
            ).fetchone()
            return row[0] if row else None


@lru_cache
def get_report_store() -> ReportStore:
    if get_settings().database_url:
        return PostgresReportStore()
    if get_settings().provider_mode != "fixture":
        from app.core.errors import ProviderError

        raise ProviderError("Configure PostgreSQL before running live investigations.")
    return MemoryReportStore()
