import io

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.services.ocr import get_ocr


def image_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (100, 50), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_image_requires_review():
    class FixedOCR:
        def extract(self, data):
            return "The demonstration library opens on Sundays."

    app.dependency_overrides[get_ocr] = FixedOCR
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/inputs/image",
                content=image_bytes(),
                headers={"Content-Type": "image/png"},
            )
        assert response.status_code == 200
        assert response.json()["review_required"] is True
    finally:
        app.dependency_overrides.clear()


def test_invalid_image_and_oversize_rejected():
    with TestClient(app) as client:
        for data, kind in [
            (b"not an image", "image/png"),
            (image_bytes(), "image/jpeg"),
            (b"x" * 5_000_001, "image/png"),
        ]:
            assert client.post(
                "/api/v1/inputs/image", content=data, headers={"Content-Type": kind}
            ).status_code in {502, 413}
