from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import app


def test_request_body_limit():
    with TestClient(app, client=("size-test", 1)) as client:
        assert (
            client.post("/api/v1/inputs/text", content=b"x" * 100001).status_code == 413
        )


def test_rate_limit_ignores_spoofed_headers(monkeypatch):
    monkeypatch.setattr(get_settings(), "requests_per_minute", 2)
    with TestClient(app, client=("rate-test", 1)) as client:
        for i in range(2):
            assert (
                client.post(
                    "/api/v1/inputs/claims",
                    json={"claim": "Some claim"},
                    headers={"X-Forwarded-For": str(i)},
                ).status_code
                == 200
            )
        assert (
            client.post(
                "/api/v1/inputs/claims", json={"claim": "Some claim"}
            ).status_code
            == 429
        )


def test_validation_errors_are_structured():
    with TestClient(app, client=("validation-test", 1)) as client:
        response = client.post("/api/v1/investigations", json={"claim": " "})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_INPUT"
