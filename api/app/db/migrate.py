from pathlib import Path

from app.core.settings import get_settings
from app.db.connection import get_connection


def migrate() -> None:
    """Apply numbered SQL files once, in one transaction under a migration lock."""
    with get_connection(get_settings()) as connection:
        connection.execute("SELECT pg_advisory_xact_lock(714902)")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY)"
        )
        completed = {
            row[0] for row in connection.execute("SELECT name FROM schema_migrations")
        }
        directory = Path(__file__).resolve().parents[2] / "migrations"
        for path in sorted(directory.glob("*.sql")):
            if path.name not in completed:
                connection.execute(path.read_text())
                connection.execute(
                    "INSERT INTO schema_migrations(name) VALUES (%s)", (path.name,)
                )


if __name__ == "__main__":
    migrate()
