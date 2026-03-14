from importlib import import_module

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from src.common.errors import ApiError
from src.common.exception_handlers import (
    api_error_handler,
    request_validation_error_handler,
)
from src.config import get_settings
from src.documents.router import router as documents_router

settings = get_settings()

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
)

app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(Exception, api_error_handler)
app.add_exception_handler(RequestValidationError, request_validation_error_handler)
app.include_router(documents_router)

try:
    debug_module = import_module("src.debug.router")
except ModuleNotFoundError:
    debug_module = None

if debug_module is not None:
    app.include_router(debug_module.router)


@app.get("/healthz", tags=["system"])
def healthz() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "document-agent-api",
        "version": "0.1.0",
    }
