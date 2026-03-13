from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class DocumentSummary(BaseSchema):
    id: UUID
    filename: str
    content_type: str = Field(alias="contentType")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class ParseResult(BaseSchema):
    markdown: str
    canonical_json: dict[str, Any] = Field(alias="canonicalJson")


class DocumentResponse(BaseSchema):
    document: DocumentSummary


class DocumentParseResponse(BaseSchema):
    document: DocumentSummary
    result: ParseResult


class DocumentListResponse(BaseSchema):
    items: list[DocumentSummary]
    total: int
    limit: int
    offset: int


class ErrorDetail(BaseSchema):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseSchema):
    error: ErrorDetail
