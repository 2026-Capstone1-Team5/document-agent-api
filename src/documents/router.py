from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse

from src.common.errors import ApiError
from src.documents.dependencies import get_document_service
from src.documents.exceptions import DocumentNotFoundError
from src.documents.schemas import (
    DocumentListResponse,
    DocumentParseResponse,
    DocumentResponse,
)
from src.documents.service import DocumentService

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.post("", response_model=DocumentParseResponse, status_code=201)
async def create_document(
    file: UploadFile = File(...),
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
        filename=filename,
        content_type=file.content_type or "application/octet-stream",
    )


@router.get("", response_model=DocumentListResponse)
def list_documents(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    filename: str | None = Query(default=None),
    service: DocumentService = Depends(get_document_service),
) -> DocumentListResponse:
    return service.list_documents(limit=limit, offset=offset, filename=filename)


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: UUID,
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    try:
        return service.get_document(document_id)
    except DocumentNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code="document_not_found",
            message=str(exc),
        ) from exc


@router.get("/{document_id}/result", response_model=DocumentParseResponse)
def get_document_result(
    document_id: UUID,
    service: DocumentService = Depends(get_document_service),
) -> DocumentParseResponse:
    try:
        return service.get_document_result(document_id)
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
    service: DocumentService = Depends(get_document_service),
) -> Response:
    try:
        result = service.get_document_result(document_id)
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
    service: DocumentService = Depends(get_document_service),
) -> Response:
    try:
        service.delete_document(document_id)
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
