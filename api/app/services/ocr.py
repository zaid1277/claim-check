import io
import warnings
from functools import lru_cache
from typing import Protocol

from PIL import Image, UnidentifiedImageError

from app.core.errors import ProviderError
from app.core.settings import Settings


class OCRProvider(Protocol):
    def extract(self, data: bytes) -> str: ...


def validate_image(data: bytes, content_type: str, settings: Settings) -> None:
    if len(data) > settings.max_image_bytes:
        raise ProviderError("Image exceeds the 5 MB upload limit.")
    formats = {"image/png": "PNG", "image/jpeg": "JPEG"}
    if content_type not in formats:
        raise ProviderError("Upload a PNG or JPEG image.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format != formats[content_type]:
                    raise ProviderError(
                        "The image content does not match its file type."
                    )
                if image.width * image.height > settings.max_image_pixels:
                    raise ProviderError("The image dimensions are too large.")
                image.verify()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ProviderError("The image is unreadable. Paste its text instead.") from exc


@lru_cache(maxsize=1)
def load_ocr():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


class LocalOCR:
    def extract(self, data: bytes) -> str:
        """OCR returns a draft, never automatically approved claim text."""
        try:
            results, _ = load_ocr()(data)
            text = "\n".join(row[1] for row in (results or []))
        except Exception as exc:
            raise ProviderError(
                "OCR is unavailable. Paste the image text instead."
            ) from exc
        if not text.strip():
            raise ProviderError("No text was recognized. Enter the claim manually.")
        return text[:30000]


def get_ocr() -> OCRProvider:
    return LocalOCR()
