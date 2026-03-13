from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from src.common.errors import ApiError
from src.common.exception_handlers import (
    api_error_handler,
    request_validation_error_handler,
)
from src.documents.router import router as documents_router


app = FastAPI(
    title="document-agent-api",
    version="0.1.0",
)

app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(Exception, api_error_handler)
app.add_exception_handler(RequestValidationError, request_validation_error_handler)
app.include_router(documents_router)


@app.get("/healthz", tags=["system"])
def healthz() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "document-agent-api",
        "version": "0.1.0",
    }
