import pytest

from app.core.settings import get_settings
from app.db.reports import MemoryReportStore, get_report_store
from app.main import app


@pytest.fixture(autouse=True)
def isolated_development_settings(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "provider_mode", "fixture")
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "requests_per_minute", 300)
    store = MemoryReportStore()
    app.dependency_overrides[get_report_store] = lambda: store
    yield
    app.dependency_overrides.clear()
