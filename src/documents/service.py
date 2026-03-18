import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, load_only

from src.documents.exceptions import DocumentNotFoundError, DocumentSourceUnavailableError
from src.documents.models import DocumentModel, DocumentResultModel
from src.documents.schemas import (
    DocumentListResponse,
    DocumentParseResponse,
    DocumentResponse,
    DocumentSummary,
    ParseResult,
)
from src.documents.utils import sanitize_document_filename
from src.storage.backends import ObjectStorage

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DocumentSourcePayload:
    filename: str
    content_type: str
    data: bytes


class DocumentService:
    def __init__(self, *, session: Session, storage: ObjectStorage) -> None:
        self.session = session
        self.storage = storage

    def list_documents(
        self,
        *,
        limit: int,
        offset: int,
        filename: str | None,
        owner_user_id: str,
    ) -> DocumentListResponse:
        statement = (
            select(DocumentModel)
            .options(
                load_only(
                    DocumentModel.id,
                    DocumentModel.source_object_key,
                    DocumentModel.filename,
                    DocumentModel.content_type,
                    DocumentModel.created_at,
                    DocumentModel.updated_at,
                )
            )
            .where(DocumentModel.owner_user_id == owner_user_id)
            .order_by(DocumentModel.created_at.desc())
        )
        count_statement = (
            select(func.count())
            .select_from(DocumentModel)
            .where(DocumentModel.owner_user_id == owner_user_id)
        )

        if filename:
            pattern = f"%{filename}%"
            statement = statement.where(DocumentModel.filename.ilike(pattern))
            count_statement = count_statement.where(DocumentModel.filename.ilike(pattern))

        items = self.session.scalars(statement.offset(offset).limit(limit)).all()
        total = self.session.scalar(count_statement) or 0

        return DocumentListResponse(
            items=[self._to_document_summary(item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
        )

    def get_document(
        self,
        document_id: UUID,
        *,
        owner_user_id: str,
    ) -> DocumentResponse:
        statement = (
            select(DocumentModel)
            .options(
                load_only(
                    DocumentModel.id,
                    DocumentModel.source_object_key,
                    DocumentModel.filename,
                    DocumentModel.content_type,
                    DocumentModel.created_at,
                    DocumentModel.updated_at,
                )
            )
            .where(
                DocumentModel.id == str(document_id),
                DocumentModel.owner_user_id == owner_user_id,
            )
        )
        document = self.session.scalars(statement).first()
        if document is None:
            raise DocumentNotFoundError(document_id)
        return DocumentResponse(document=self._to_document_summary(document))

    def get_document_source(
        self,
        document_id: UUID,
        *,
        owner_user_id: str,
    ) -> DocumentSourcePayload:
        statement = (
            select(DocumentModel)
            .options(
                load_only(
                    DocumentModel.id,
                    DocumentModel.source_object_key,
                    DocumentModel.filename,
                    DocumentModel.content_type,
                )
            )
            .where(
                DocumentModel.id == str(document_id),
                DocumentModel.owner_user_id == owner_user_id,
            )
        )
        document = self.session.scalars(statement).first()
        if document is None:
            raise DocumentNotFoundError(document_id)

        return DocumentSourcePayload(
            filename=document.filename,
            content_type=document.content_type,
            data=self._load_source_payload(document),
        )

    def get_document_result(
        self,
        document_id: UUID,
        *,
        owner_user_id: str,
    ) -> DocumentParseResponse:
        statement = (
            select(DocumentModel)
            .options(
                load_only(
                    DocumentModel.id,
                    DocumentModel.source_object_key,
                    DocumentModel.filename,
                    DocumentModel.content_type,
                    DocumentModel.created_at,
                    DocumentModel.updated_at,
                ),
                joinedload(DocumentModel.result).load_only(
                    DocumentResultModel.document_id,
                    DocumentResultModel.markdown,
                    DocumentResultModel.canonical_json,
                    DocumentResultModel.markdown_object_key,
                    DocumentResultModel.canonical_json_object_key,
                ),
            )
            .where(
                DocumentModel.id == str(document_id),
                DocumentModel.owner_user_id == owner_user_id,
            )
        )
        document = self.session.scalars(statement).first()
        if document is None or document.result is None:
            raise DocumentNotFoundError(document_id)
        markdown, canonical_json = self._load_result_payload(document)
        return self._to_document_parse_response(
            document,
            markdown=markdown,
            canonical_json=canonical_json,
        )

    def create_document(
        self,
        *,
        owner_user_id: str,
        filename: str,
        content_type: str,
        file_data: bytes,
    ) -> DocumentParseResponse:
        document_id = str(uuid4())
        title = Path(filename).stem.replace("_", " ").replace("-", " ").strip() or "Mock Document"
        safe_filename = sanitize_document_filename(filename)
        source_object_key = f"documents/{document_id}/source/{safe_filename}"
        markdown_object_key = f"documents/{document_id}/result/result.md"
        canonical_json_object_key = f"documents/{document_id}/result/result.json"
        markdown_content = self._build_markdown(title=title, filename=filename)
        canonical_json_content = self._build_canonical_json(title=title, filename=filename)
        uploaded_keys: list[str] = []

        try:
            self.storage.put_bytes(
                key=source_object_key,
                data=file_data,
                content_type=content_type,
            )
            uploaded_keys.append(source_object_key)
            self.storage.put_bytes(
                key=markdown_object_key,
                data=markdown_content.encode("utf-8"),
                content_type="text/markdown",
            )
            uploaded_keys.append(markdown_object_key)
            self.storage.put_bytes(
                key=canonical_json_object_key,
                data=json.dumps(canonical_json_content, ensure_ascii=False).encode("utf-8"),
                content_type="application/json",
            )
            uploaded_keys.append(canonical_json_object_key)

            document = DocumentModel(
                id=document_id,
                owner_user_id=owner_user_id,
                source_object_key=source_object_key,
                filename=filename,
                content_type=content_type,
                file_data=None,
            )
            document.result = DocumentResultModel(
                document_id=document_id,
                markdown=None,
                canonical_json=None,
                markdown_object_key=markdown_object_key,
                canonical_json_object_key=canonical_json_object_key,
            )

            self.session.add(document)
            self.session.commit()
        except Exception as exc:
            self.session.rollback()
            cleanup_failed_keys = self._delete_objects_best_effort(
                uploaded_keys,
                retries=3,
            )
            if cleanup_failed_keys:
                recovered_document = self._persist_document_after_incomplete_create_cleanup(
                    document_id=document_id,
                    owner_user_id=owner_user_id,
                    filename=filename,
                    content_type=content_type,
                    file_data=file_data,
                    markdown_content=markdown_content,
                    canonical_json_content=canonical_json_content,
                    source_object_key=source_object_key,
                    markdown_object_key=markdown_object_key,
                    canonical_json_object_key=canonical_json_object_key,
                    remaining_object_keys=cleanup_failed_keys,
                )
                if recovered_document is not None:
                    logger.warning(
                        (
                            "create cleanup was incomplete, persisted fallback "
                            "document for document_id=%s keys=%s"
                        ),
                        document_id,
                        ",".join(cleanup_failed_keys),
                    )
                    return self._to_document_parse_response(
                        recovered_document,
                        markdown=markdown_content,
                        canonical_json=canonical_json_content,
                    )

                logger.error(
                    "create cleanup failed for document_id=%s keys=%s",
                    document_id,
                    ",".join(cleanup_failed_keys),
                )
                msg = (
                    "document creation failed and object cleanup is incomplete; "
                    f"document_id={document_id}, failed_keys={','.join(cleanup_failed_keys)}"
                )
                raise RuntimeError(msg) from exc
            raise

        self.session.refresh(document)
        self.session.refresh(document, attribute_names=["result"])

        return self._to_document_parse_response(
            document,
            markdown=markdown_content,
            canonical_json=canonical_json_content,
        )

    def delete_document(self, document_id: UUID, *, owner_user_id: str) -> None:
        statement = select(DocumentModel).where(
            DocumentModel.id == str(document_id),
            DocumentModel.owner_user_id == owner_user_id,
        )
        document = self.session.scalars(statement).first()
        if document is None:
            raise DocumentNotFoundError(document_id)

        object_keys = self._collect_object_keys(document)

        backup_payloads, deleted_keys = self._delete_objects_strict(object_keys)
        try:
            self.session.delete(document)
            self.session.commit()
        except Exception as exc:
            self.session.rollback()
            restore_failed_keys = self._restore_objects_best_effort(
                deleted_keys,
                backup_payloads,
            )
            if restore_failed_keys:
                logger.error(
                    "delete rollback after commit failure failed for keys=%s",
                    ",".join(restore_failed_keys),
                )
                msg = "database commit failed and object rollback also failed"
                raise RuntimeError(msg) from exc
            raise

    @staticmethod
    def _build_markdown(*, title: str, filename: str) -> str:
        return (
            f"# {title}\n\n"
            "This is a mock parsed document result.\n\n"
            f"- source filename: `{filename}`\n"
            "- parser mode: `mock`\n"
        )

    @staticmethod
    def _build_canonical_json(*, title: str, filename: str) -> dict:
        return {
            "document": {
                "title": title,
                "sourceFilename": filename,
            },
            "pages": [
                {
                    "pageNumber": 1,
                    "blocks": [
                        {
                            "type": "heading",
                            "text": title,
                        },
                        {
                            "type": "paragraph",
                            "text": "This is a mock parsed document result.",
                        },
                    ],
                }
            ],
        }

    @staticmethod
    def _to_document_summary(document: DocumentModel) -> DocumentSummary:
        return DocumentSummary(
            id=UUID(document.id),
            filename=document.filename,
            contentType=document.content_type,
            createdAt=document.created_at,
            updatedAt=document.updated_at,
        )

    def _to_document_parse_response(
        self,
        document: DocumentModel,
        *,
        markdown: str,
        canonical_json: dict[str, Any],
    ) -> DocumentParseResponse:
        return DocumentParseResponse(
            document=self._to_document_summary(document),
            result=ParseResult(
                markdown=markdown,
                canonicalJson=canonical_json,
            ),
        )

    def _load_result_payload(self, document: DocumentModel) -> tuple[str, dict[str, Any]]:
        if document.result is None:
            raise DocumentNotFoundError(UUID(document.id))

        markdown = self._load_markdown_payload(document.result)
        canonical_json = self._load_canonical_json_payload(document.result)
        if markdown is None or canonical_json is None:
            raise DocumentNotFoundError(UUID(document.id))
        return markdown, canonical_json

    def _load_source_payload(self, document: DocumentModel) -> bytes:
        if document.source_object_key:
            try:
                return self.storage.get_bytes(key=document.source_object_key)
            except Exception as exc:
                if document.file_data is None:
                    logger.warning(
                        "failed to read source object key=%s with no inline fallback",
                        document.source_object_key,
                        exc_info=exc,
                    )
                    raise DocumentSourceUnavailableError(UUID(document.id)) from exc
                logger.warning(
                    "failed to read source object key=%s, using inline fallback",
                    document.source_object_key,
                    exc_info=exc,
                )

        if document.file_data is not None:
            return document.file_data

        raise DocumentSourceUnavailableError(UUID(document.id))

    def _collect_object_keys(self, document: DocumentModel) -> list[str]:
        keys: list[str] = []
        if document.source_object_key:
            keys.append(document.source_object_key)
        if document.result is not None:
            if document.result.markdown_object_key:
                keys.append(document.result.markdown_object_key)
            if document.result.canonical_json_object_key:
                keys.append(document.result.canonical_json_object_key)
        return keys

    def _delete_objects_best_effort(self, keys: list[str], *, retries: int = 1) -> list[str]:
        failed: list[str] = []
        for key in keys:
            deleted = False
            for attempt in range(retries):
                try:
                    self.storage.delete_object(key=key)
                    deleted = True
                    break
                except Exception as exc:
                    if attempt == retries - 1:
                        logger.warning(
                            "best-effort storage cleanup failed for key=%s",
                            key,
                            exc_info=exc,
                        )
            if not deleted:
                failed.append(key)
        return failed

    def _persist_document_after_incomplete_create_cleanup(
        self,
        *,
        document_id: str,
        owner_user_id: str,
        filename: str,
        content_type: str,
        file_data: bytes,
        markdown_content: str,
        canonical_json_content: dict[str, Any],
        source_object_key: str,
        markdown_object_key: str,
        canonical_json_object_key: str,
        remaining_object_keys: list[str],
    ) -> DocumentModel | None:
        remaining_keys = set(remaining_object_keys)
        document = DocumentModel(
            id=document_id,
            owner_user_id=owner_user_id,
            source_object_key=source_object_key if source_object_key in remaining_keys else None,
            filename=filename,
            content_type=content_type,
            file_data=file_data,
        )
        document.result = DocumentResultModel(
            document_id=document_id,
            markdown=markdown_content,
            canonical_json=canonical_json_content,
            markdown_object_key=markdown_object_key
            if markdown_object_key in remaining_keys
            else None,
            canonical_json_object_key=(
                canonical_json_object_key if canonical_json_object_key in remaining_keys else None
            ),
        )
        self.session.add(document)
        try:
            self.session.commit()
        except Exception as exc:
            self.session.rollback()
            logger.error(
                (
                    "failed to persist fallback document after incomplete "
                    "create cleanup for document_id=%s"
                ),
                document_id,
                exc_info=exc,
            )
            return None
        self.session.refresh(document)
        self.session.refresh(document, attribute_names=["result"])
        return document

    def _delete_objects_strict(self, keys: list[str]) -> tuple[dict[str, bytes], list[str]]:
        backup_payloads: dict[str, bytes] = {}
        for key in keys:
            try:
                backup_payloads[key] = self.storage.get_bytes(key=key)
            except Exception as exc:
                if self._is_missing_object_error(exc):
                    continue
                raise

        deleted_keys: list[str] = []
        try:
            for key in keys:
                try:
                    self.storage.delete_object(key=key)
                    deleted_keys.append(key)
                except Exception as exc:
                    if self._is_missing_object_error(exc):
                        continue
                    raise
        except Exception as exc:
            restore_failed_keys = self._restore_objects_best_effort(
                deleted_keys,
                backup_payloads,
            )
            if restore_failed_keys:
                logger.error(
                    "strict delete rollback failed for keys=%s",
                    ",".join(restore_failed_keys),
                )
                msg = "storage delete failed and object rollback also failed"
                raise RuntimeError(msg) from exc
            raise
        return backup_payloads, deleted_keys

    def _restore_objects_best_effort(
        self,
        keys: list[str],
        backup_payloads: dict[str, bytes],
    ) -> list[str]:
        failed: list[str] = []
        for key in keys:
            data = backup_payloads.get(key)
            if data is None:
                failed.append(key)
                continue
            try:
                self.storage.put_bytes(
                    key=key,
                    data=data,
                    content_type=self._content_type_for_key(key),
                )
            except Exception as exc:
                logger.warning(
                    "best-effort storage rollback failed for key=%s",
                    key,
                    exc_info=exc,
                )
                failed.append(key)
        return failed

    def _load_markdown_payload(self, result: DocumentResultModel) -> str | None:
        if result.markdown_object_key:
            try:
                return self.storage.get_bytes(key=result.markdown_object_key).decode("utf-8")
            except Exception as exc:
                if result.markdown is None:
                    raise
                logger.warning(
                    "failed to read markdown object key=%s, using inline fallback",
                    result.markdown_object_key,
                    exc_info=exc,
                )
        return result.markdown

    def _load_canonical_json_payload(self, result: DocumentResultModel) -> dict[str, Any] | None:
        if result.canonical_json_object_key:
            try:
                canonical_json_raw = self.storage.get_bytes(
                    key=result.canonical_json_object_key,
                ).decode("utf-8")
                canonical_json = json.loads(canonical_json_raw)
                if not isinstance(canonical_json, dict):
                    raise ValueError("canonical json payload must be a JSON object")
                return canonical_json
            except Exception as exc:
                if result.canonical_json is None:
                    raise
                logger.warning(
                    "failed to read canonical json object key=%s, using inline fallback",
                    result.canonical_json_object_key,
                    exc_info=exc,
                )
        return result.canonical_json

    @staticmethod
    def _content_type_for_key(key: str) -> str:
        if key.endswith(".md"):
            return "text/markdown"
        if key.endswith(".json"):
            return "application/json"
        return "application/octet-stream"

    @staticmethod
    def _is_missing_object_error(exc: Exception) -> bool:
        if isinstance(exc, (FileNotFoundError, KeyError)):
            return True

        response = getattr(exc, "response", None)
        if isinstance(response, dict):
            error = response.get("Error")
            if isinstance(error, dict):
                code = str(error.get("Code", "")).lower()
                if code in {"nosuchkey", "notfound", "404"}:
                    return True
        return False
