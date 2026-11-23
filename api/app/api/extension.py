from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import AnyHttpUrl, Field

from app.db.reports import ReportStore, get_report_store
from app.schemas.investigation import ClaimInput, Investigation
from app.services.investigation import investigate

router = APIRouter(tags=["extension"])


class ExtensionInput(ClaimInput):
    source_url: AnyHttpUrl | None = None
    page_title: str = Field(default="", max_length=500)


@router.post("/extension/check", response_model=Investigation)
def extension_check(
    body: ExtensionInput, store: Annotated[ReportStore, Depends(get_report_store)]
):
    result = investigate(body.claim)
    result.input_type = "browser_selection"
    result.source_url = str(body.source_url) if body.source_url else None
    result.model_metadata["page_url"] = result.source_url or ""
    result.model_metadata["page_title"] = body.page_title
    store.save(result)
    return result
