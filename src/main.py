from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from src.auth.router import router as auth_router
from src.common.errors import ApiError
from src.common.exception_handlers import (
    api_error_handler,
    request_validation_error_handler,
)
from src.config import get_settings
from src.documents.router import router as documents_router
from src.model_registry import load_model_registry
from src.parse_jobs.router import router as parse_jobs_router

settings = get_settings()
load_model_registry()

app = FastAPI(
    title="document-agent-api",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(Exception, api_error_handler)
app.add_exception_handler(RequestValidationError, request_validation_error_handler)
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(parse_jobs_router)


@app.get("/healthz", tags=["system"])
def healthz() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "document-agent-api",
        "version": "0.1.0",
    }
