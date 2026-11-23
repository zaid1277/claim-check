from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

from app.core.settings import Settings


class DatabaseNotConfiguredError(Exception):
    pass


@contextmanager
def get_connection(settings: Settings) -> Iterator[psycopg.Connection]:
    """Open a short-lived connection and always close it after use."""
    if settings.database_url is None:
        raise DatabaseNotConfiguredError

    # Short-lived transactions keep connection ownership explicit for this small API.
    with psycopg.connect(
        str(settings.database_url),
        connect_timeout=3,
        options="-c statement_timeout=3000",
    ) as connection:
        yield connection


def check_database(settings: Settings) -> None:
    """Raise if PostgreSQL cannot accept and execute a simple query."""
    with get_connection(settings) as connection:
        connection.execute("SELECT 1").fetchone()
