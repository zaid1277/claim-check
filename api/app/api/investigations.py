from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.core.settings import get_settings
from app.db.reports import ReportStore, get_report_store
from app.schemas.inputs import InvestigationInput
from app.schemas.investigation import ClaimInput, Investigation
from app.services.investigation import investigate

router = APIRouter(tags=["investigations"])


@router.post("/inputs/claims")
def claims(body: ClaimInput):
    return {"claims": [body.claim]}


@router.post("/investigations", response_model=Investigation)
def create_investigation(
    body: InvestigationInput, store: Annotated[ReportStore, Depends(get_report_store)]
):
    if len(body.claims) > get_settings().max_claims:
        raise HTTPException(422, "Too many selected claims for this server.")
    results = [investigate(claim) for claim in body.claims]
    result = results[0]
    result.assessments = [
        assessment for item in results for assessment in item.assessments
    ]
    result.input_type = body.input_type
    result.source_url = str(body.source_url) if body.source_url else None
    result.raw_text = body.raw_text or "\n".join(body.claims)
    store.save(result)
    return result
