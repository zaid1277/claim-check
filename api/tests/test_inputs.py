import pytest
from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.main import app
from app.services.claim_extraction import SentenceClaimExtractor


def test_sentence_candidates_require_review():
    claims = SentenceClaimExtractor(Settings(_env_file=None)).extract(
        "Does this happen on Sunday? The demonstration library opens on Sundays."
    )
    assert claims == ["The demonstration library opens on Sundays."]


def test_text_and_multiclaim_routes():
    with TestClient(app) as client:
        proposal = client.post(
            "/api/v1/inputs/text",
            json={"text": "The demonstration library opens on Sundays."},
        )
        assert proposal.status_code == 200
        response = client.post(
            "/api/v1/investigations", json={"claims": proposal.json()["claims"]}
        )
        assert response.status_code == 200
        assert len(response.json()["assessments"]) == 1
        assert (
            client.post("/api/v1/investigations", json={"claims": []}).status_code
            == 422
        )
        assert (
            client.post(
                "/api/v1/inputs/url", json={"url": "http://127.0.0.1"}
            ).status_code
            == 502
        )


@pytest.mark.parametrize("count", [1, 5])
def test_article_proposals_create_and_reload_selected_investigation(monkeypatch, count):
    from uuid import UUID

    from app.services.article_extraction import Article

    url = "https://en.wikipedia.org/wiki/Eiffel_Tower"
    text = " ".join(
        [
            "The Eiffel Tower is in Paris, France.",
            "The tower was built for the 1889 World's Fair.",
            "Gustave Eiffel was an engineer.",
            "The tower stands on the Champ de Mars.",
            "Visitors can climb the Eiffel Tower.",
        ]
    )
    monkeypatch.setattr(
        "app.api.inputs.extract_article",
        lambda source: Article(source, "Eiffel Tower", "en.wikipedia.org", text),
    )
    with TestClient(app) as client:
        proposal = client.post("/api/v1/inputs/url", json={"url": url})
        assert proposal.status_code == 200
        data = proposal.json()
        assert len(data["claims"]) == 5
        selected = data["claims"][:count]
        response = client.post(
            "/api/v1/investigations",
            json={
                "input_type": "url",
                "source_url": url,
                "raw_text": data["text"],
                "claims": selected,
            },
        )
        assert response.status_code == 200
        result = response.json()
        assert str(UUID(result["id"])) == result["id"]
        assert result["input_type"] == "url"
        assert result["source_url"] == url
        assert [a["claim"] for a in result["assessments"]] == selected
        restored = client.get(f"/api/v1/investigations/{result['id']}")
        assert restored.status_code == 200
        assert restored.json() == result
