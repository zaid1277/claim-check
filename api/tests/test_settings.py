import pytest
from pydantic import ValidationError

from app.core.settings import Settings


def test_database_url_comes_from_environment(monkeypatch):
    url = "postgresql://test:test@localhost:5432/claim_check"
    monkeypatch.setenv("DATABASE_URL", url)
    assert str(Settings(_env_file=None).database_url) == url


def test_non_postgresql_url_is_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="sqlite:///local.db")
