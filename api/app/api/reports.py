from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.db.reports import ReportStore, get_report_store
from app.schemas.investigation import Investigation

router = APIRouter(tags=["reports"])
Store = Annotated[ReportStore, Depends(get_report_store)]


@router.get("/investigations/{identifier}", response_model=Investigation)
def get_investigation(identifier: UUID, store: Store):
    result = store.get(str(identifier))
    if result is None:
        raise HTTPException(404, "Investigation not found.")
    return result


@router.post("/investigations/{identifier}/share")
def share(identifier: UUID, store: Store):
    slug = store.publish(identifier)
    if slug is None:
        raise HTTPException(404, "Investigation not found.")
    return {"share_slug": slug}


@router.get("/reports/{slug}", response_model=Investigation)
def public_report(slug: str, store: Store):
    result = store.get(slug, shared=True)
    if result is None:
        raise HTTPException(404, "Report not found.")
    return result
