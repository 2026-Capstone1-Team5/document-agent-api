from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from src.documents.schemas import BaseSchema
from src.parser_backends import ParserBackend

ParseJobStatus = Literal["queued", "processing", "succeeded", "failed"]


class ParseJobSummary(BaseSchema):
    id: UUID
    filename: str
    content_type: str = Field(alias="contentType")
    parser_backend: ParserBackend = Field(alias="parserBackend")
    status: ParseJobStatus
    document_id: UUID | None = Field(alias="documentId", default=None)
    error_code: str | None = Field(alias="errorCode", default=None)
    error_message: str | None = Field(alias="errorMessage", default=None)
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    started_at: datetime | None = Field(alias="startedAt", default=None)
    finished_at: datetime | None = Field(alias="finishedAt", default=None)


class ParseJobResponse(BaseSchema):
    job: ParseJobSummary
