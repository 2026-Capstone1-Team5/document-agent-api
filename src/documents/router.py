from typing import Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse

from src.auth.dependencies import get_current_document_user
from src.auth.models import UserModel
from src.common.errors import ApiError
from src.documents.dependencies import get_document_service
from src.documents.exceptions import DocumentNotFoundError, DocumentSourceUnavailableError
from src.documents.schemas import (
    DocumentListResponse,
    DocumentParseResponse,
    DocumentResponse,
)
from src.documents.service import DocumentService, sanitize_filename

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.post("", response_model=DocumentParseResponse, status_code=201)
async def create_document(
    file: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_document_user),
    service: DocumentService = Depends(get_document_service),
) -> DocumentParseResponse:
    filename = file.filename or ""
    if not filename.strip():
        raise ApiError(
            status_code=400,
            code="missing_filename",
            message="File name is required.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise ApiError(
            status_code=400,
            code="empty_file",
            message="Uploaded file is empty.",
        )

    if not _is_supported_file(filename=filename, content_type=file.content_type):
        raise ApiError(
            status_code=415,
            code="unsupported_file_type",
            message="Unsupported file type.",
            details={"filename": filename},
        )

    return service.create_document(
        owner_user_id=current_user.id,
        filename=filename,
        content_type=file.content_type or "application/octet-stream",
        file_data=file_bytes,
    )


@router.get("", response_model=DocumentListResponse)
def list_documents(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    filename: str | None = Query(default=None),
    current_user: UserModel = Depends(get_current_document_user),
    service: DocumentService = Depends(get_document_service),
) -> DocumentListResponse:
    return service.list_documents(
        limit=limit,
        offset=offset,
        filename=filename,
        owner_user_id=current_user.id,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: UUID,
    current_user: UserModel = Depends(get_current_document_user),
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    try:
        return service.get_document(document_id, owner_user_id=current_user.id)
    except DocumentNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code="document_not_found",
            message=str(exc),
        ) from exc


@router.get(
    "/{document_id}/source",
    response_class=Response,
    responses={
        200: {
            "description": "Original source file bytes.",
            "content": {
                "application/pdf": {"schema": {"type": "string", "format": "binary"}},
                "application/x-hwp": {"schema": {"type": "string", "format": "binary"}},
                "image/png": {"schema": {"type": "string", "format": "binary"}},
                "image/jpeg": {"schema": {"type": "string", "format": "binary"}},
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}},
            },
        }
    },
)
def get_document_source(
    document_id: UUID,
    disposition: Literal["inline", "attachment"] = Query(default="inline"),
    current_user: UserModel = Depends(get_current_document_user),
    service: DocumentService = Depends(get_document_service),
) -> Response:
    try:
        source = service.get_document_source(document_id, owner_user_id=current_user.id)
    except DocumentNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code="document_not_found",
            message=str(exc),
        ) from exc
    except DocumentSourceUnavailableError as exc:
        raise ApiError(
            status_code=500,
            code="source_file_unavailable",
            message=str(exc),
        ) from exc

    return Response(
        content=source.data,
        media_type=source.content_type,
        headers={
            "Content-Disposition": _build_content_disposition(
                disposition=disposition,
                filename=source.filename,
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{document_id}/result", response_model=DocumentParseResponse)
def get_document_result(
    document_id: UUID,
    current_user: UserModel = Depends(get_current_document_user),
    service: DocumentService = Depends(get_document_service),
) -> DocumentParseResponse:
    try:
        return service.get_document_result(document_id, owner_user_id=current_user.id)
    except DocumentNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code="document_not_found",
            message=str(exc),
        ) from exc


@router.get("/{document_id}/download")
def download_document_result(
    document_id: UUID,
    format: str = Query(...),
    current_user: UserModel = Depends(get_current_document_user),
    service: DocumentService = Depends(get_document_service),
) -> Response:
    try:
        result = service.get_document_result(document_id, owner_user_id=current_user.id)
    except DocumentNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code="document_not_found",
            message=str(exc),
        ) from exc

    if format == "markdown":
        return PlainTextResponse(
            content=result.result.markdown,
            media_type="text/markdown",
            headers={"Content-Disposition": (f'attachment; filename="{result.document.id}.md"')},
        )

    if format == "json":
        return JSONResponse(
            content=result.result.canonical_json,
            headers={"Content-Disposition": (f'attachment; filename="{result.document.id}.json"')},
        )

    raise ApiError(
        status_code=406,
        code="unsupported_download_format",
        message="Unsupported download format.",
        details={"format": format},
    )


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: UUID,
    current_user: UserModel = Depends(get_current_document_user),
    service: DocumentService = Depends(get_document_service),
) -> Response:
    try:
        service.delete_document(document_id, owner_user_id=current_user.id)
    except DocumentNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code="document_not_found",
            message=str(exc),
        ) from exc
    return Response(status_code=204)


def _is_supported_file(*, filename: str, content_type: str | None) -> bool:
    supported_extensions = {
        ".pdf",
        ".hwp",
        ".hwpx",
        ".png",
        ".jpg",
        ".jpeg",
    }
    supported_content_types = {
        "application/pdf",
        "application/x-hwp",
        "application/haansoft-hwp",
        "application/vnd.hancom.hwp",
        "application/haansoft-hwpx",
        "application/vnd.hancom.hwpx",
        "image/png",
        "image/jpeg",
    }
    lowered_filename = filename.lower()
    if any(lowered_filename.endswith(extension) for extension in supported_extensions):
        return True
    if content_type in supported_content_types:
        return True
    if content_type and content_type.startswith("image/"):
        return True
    return False


def _build_content_disposition(*, disposition: str, filename: str) -> str:
    safe_filename = sanitize_filename(filename)
    ascii_fallback = "".join(
        character
        if character.isascii() and character not in {'"', "\\"} and 32 <= ord(character) < 127
        else "_"
        for character in safe_filename
    ).strip(" .")
    if not ascii_fallback:
        ascii_fallback = "download.bin"

    encoded_filename = quote(safe_filename, safe="")
    return f"{disposition}; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded_filename}"
