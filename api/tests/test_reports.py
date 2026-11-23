from fastapi.testclient import TestClient

from app.db.reports import MemoryReportStore, get_report_store
from app.main import app


def test_report_published_explicitly_and_read_only():
    app.dependency_overrides[get_report_store] = MemoryReportStore
    store = MemoryReportStore()
    app.dependency_overrides[get_report_store] = lambda: store
    try:
        with TestClient(app) as client:
            report = client.post(
                "/api/v1/investigations",
                json={"claim": "The demonstration library opens on Sundays."},
            ).json()
            assert report["share_slug"] is None
            identifier = report["id"]
            slug = client.post(f"/api/v1/investigations/{identifier}/share").json()[
                "share_slug"
            ]
            assert (
                client.post(f"/api/v1/investigations/{identifier}/share").json()[
                    "share_slug"
                ]
                == slug
            )
            assert (
                client.get(f"/api/v1/reports/{slug}").json()["assessments"]
                == report["assessments"]
            )
            assert client.post(f"/api/v1/reports/{slug}").status_code == 405
            assert client.get("/api/v1/reports/missing").status_code == 404
    finally:
        app.dependency_overrides.clear()
