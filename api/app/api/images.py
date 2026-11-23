from typing import Annotated

from fastapi import APIRouter, Depends, Request
from starlette.concurrency import run_in_threadpool

from app.core.errors import ProviderError
from app.core.settings import get_settings
from app.services.ocr import OCRProvider, get_ocr, validate_image

router = APIRouter(tags=["inputs"])


@router.post("/inputs/image")
async def image_input(request: Request, ocr: Annotated[OCRProvider, Depends(get_ocr)]):
    settings = get_settings()
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > settings.max_image_bytes:
            raise ProviderError("Image exceeds the 5 MB upload limit.")
    raw = bytes(data)
    validate_image(raw, request.headers.get("content-type", ""), settings)
    text = await run_in_threadpool(ocr.extract, raw)
    return {"text": text, "review_required": True}
