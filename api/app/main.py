import psycopg
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.extension import router as extension_router
from app.api.health import router as health_router
from app.api.images import router as image_router
from app.api.inputs import router as input_router
from app.api.investigations import router as investigation_router
from app.api.reports import router as report_router
from app.api.setup import router as setup_router
from app.core.errors import ProviderError
from app.core.security import RequestLimits

app = FastAPI(title="Claim Check API", version="0.1.0")
app.add_middleware(RequestLimits)
app.include_router(setup_router, prefix="/api/v1")
app.include_router(extension_router, prefix="/api/v1")
app.include_router(report_router, prefix="/api/v1")
app.include_router(image_router, prefix="/api/v1")
app.include_router(input_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api/v1")
app.include_router(investigation_router, prefix="/api/v1")


@app.exception_handler(ProviderError)
async def provider_error(request: Request, exc: ProviderError):
    return JSONResponse(
        status_code=502,
        content={"error": {"code": "PROVIDER_UNAVAILABLE", "message": str(exc)}},
    )


@app.exception_handler(psycopg.Error)
async def database_error(request: Request, exc: psycopg.Error):
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "DATABASE_UNAVAILABLE",
                "message": "The report database is unavailable.",
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def invalid_input(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "INVALID_INPUT",
                "message": (
                    "Enter a valid search provider and API key."
                    if request.url.path == "/api/v1/setup/providers"
                    else "Check the input length, format and selected claims."
                ),
            }
        },
    )


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "REQUEST_FAILED", "message": str(exc.detail)}},
    )
