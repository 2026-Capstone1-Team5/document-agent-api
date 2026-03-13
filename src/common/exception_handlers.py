from collections.abc import Sequence
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.common.errors import ApiError


async def api_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, ApiError):
        return _error_response(
            status_code=500,
            code="internal_server_error",
            message="Unexpected server error.",
        )

    return _error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def request_validation_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        return _error_response(
            status_code=500,
            code="internal_server_error",
            message="Unexpected server error.",
        )

    errors = exc.errors()

    if _is_documents_upload_validation_error(request=request, errors=errors):
        return _error_response(
            status_code=400,
            code="malformed_multipart_request",
            message="Malformed multipart request.",
            details={"errors": errors},
        )

    return _error_response(
        status_code=422,
        code="request_validation_error",
        message="Request validation error.",
        details={"errors": errors},
    )


def _is_documents_upload_validation_error(
    *,
    request: Request,
    errors: Sequence[Any],
) -> bool:
    normalized_path = request.url.path.rstrip("/")
    if request.method != "POST" or normalized_path != "/api/v1/documents":
        return False

    return any(
        isinstance(error, dict)
        and tuple(error.get("loc", ()))[:2] == ("body", "file")
        for error in errors
    )


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details,
            }
        },
    )
