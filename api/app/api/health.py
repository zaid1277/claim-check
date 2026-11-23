from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.settings import Settings, get_settings
from app.db.connection import DatabaseNotConfiguredError, check_database
from app.schemas.health import (
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    ReadinessResponse,
)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ErrorResponse}},
)
def readiness(settings: Annotated[Settings, Depends(get_settings)]):
    try:
        check_database(settings)
    except (DatabaseNotConfiguredError, psycopg.Error):
        # Connection errors can contain hostnames and credentials; keep them private.
        error = ErrorResponse(
            error=ErrorDetail(
                code="DATABASE_UNAVAILABLE",
                message="Database is unavailable or not configured.",
            )
        )
        return JSONResponse(status_code=503, content=error.model_dump())
    return ReadinessResponse()
