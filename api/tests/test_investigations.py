from fastapi.testclient import TestClient

from app.main import app
from app.services.investigation import DEMO_CLAIM


def test_typed_claim_fixture():
    with TestClient(app) as client:
        response = client.post("/api/v1/investigations", json={"claim": DEMO_CLAIM})
    assert response.status_code == 200
    assert response.json()["mode"] == "fixture"
    assert response.json()["assessments"][0]["verdict"] == "SUPPORTED"


def test_unknown_claim_does_not_invent_evidence():
    with TestClient(app) as client:
        result = client.post(
            "/api/v1/investigations", json={"claim": "An unknown claim."}
        ).json()
    assert result["assessments"][0]["evidence"] == []
    assert result["assessments"][0]["verdict"] == "INSUFFICIENT_EVIDENCE"


def test_blank_claim_rejected():
    with TestClient(app) as client:
        assert (
            client.post("/api/v1/investigations", json={"claim": "   "}).status_code
            == 422
        )
