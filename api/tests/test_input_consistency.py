"""Input adapters must preserve the same reviewed claim through saved reports."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.services import article_extraction
from app.services.investigation import DEMO_CLAIM
from app.services.ocr import get_ocr


@pytest.mark.parametrize("input_type", ["claim", "text", "url", "image"])
def test_reviewed_claim_has_consistent_saved_assessment(monkeypatch, input_type):
    # Only external HTML and OCR are fixed. Extraction, proposal, investigation,
    # serialization, report reload and sharing use the real application routes.
    url = "https://example.org/library"
    article = f"{DEMO_CLAIM}\nVisitors can read the published opening schedule."
    monkeypatch.setattr(
        article_extraction,
        "fetch_html",
        lambda source: (
            f"<html><body><article><p>{DEMO_CLAIM}</p>"
            "<p>Visitors can read the published opening schedule.</p>"
            "</article></body></html>",
            source,
        ),
    )

    class DraftOCR:
        def extract(self, data):
            return article.replace("demonstration", "demonstratlon")

    app.dependency_overrides[get_ocr] = DraftOCR
    with TestClient(app) as client:
        baseline = client.post(
            "/api/v1/investigations", json={"claims": [DEMO_CLAIM]}
        ).json()["assessments"]
        if input_type == "claim":
            proposal = client.post("/api/v1/inputs/claims", json={"claim": DEMO_CLAIM})
        elif input_type == "url":
            proposal = client.post("/api/v1/inputs/url", json={"url": url})
        else:
            if input_type == "image":
                image = io.BytesIO()
                Image.new("RGB", (100, 50), "white").save(image, format="PNG")
                draft = client.post(
                    "/api/v1/inputs/image",
                    content=image.getvalue(),
                    headers={"Content-Type": "image/png"},
                )
                assert draft.status_code == 200
                assert draft.json()["review_required"] is True
                assert "demonstratlon" in draft.json()["text"]
                # The user corrects the draft before proposing or approving claims.
            proposal = client.post("/api/v1/inputs/text", json={"text": article})
        assert proposal.status_code == 200
        assert proposal.json()["claims"]
        response = client.post(
            "/api/v1/investigations",
            json={
                "input_type": input_type,
                "raw_text": article,
                "source_url": url if input_type == "url" else None,
                "claims": [DEMO_CLAIM],
            },
        )
        assert response.status_code == 200
        result = response.json()
        assert result["input_type"] == input_type
        assert result["assessments"] == baseline
        assert result["assessments"][0]["verdict"] == "SUPPORTED"
        restored = client.get(f"/api/v1/investigations/{result['id']}")
        assert restored.status_code == 200
        assert restored.json() == result
        shared = client.post(f"/api/v1/investigations/{result['id']}/share")
        assert shared.status_code == 200
        report = client.get(f"/api/v1/reports/{shared.json()['share_slug']}")
        assert report.status_code == 200
        assert report.json()["assessments"] == baseline
