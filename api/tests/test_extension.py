from fastapi.testclient import TestClient

from app.main import app


def test_extension_preserves_context_and_uses_shared_pipeline():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/extension/check",
            json={
                "claim": "The demonstration library opens on Sundays.",
                "source_url": "https://example.org/article",
                "page_title": "Example",
            },
        )
    assert response.status_code == 200
    result = response.json()
    assert result["model_metadata"]["page_title"] == "Example"
    assert result["assessments"][0]["verdict"] == "SUPPORTED"
