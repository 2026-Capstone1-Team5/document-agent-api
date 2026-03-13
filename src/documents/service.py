from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from src.documents.exceptions import DocumentNotFoundError
from src.documents.schemas import (
    DocumentListResponse,
    DocumentParseResponse,
    DocumentResponse,
    DocumentSummary,
    ParseResult,
)


@dataclass(slots=True)
class _StoredDocument:
    document: DocumentSummary
    result: ParseResult


class DocumentService:
    def __init__(self, *, items: list[_StoredDocument] | None = None) -> None:
        self._items: dict[UUID, _StoredDocument] = {
            item.document.id: item for item in (items or [])
        }

    @classmethod
    def seeded(cls) -> "DocumentService":
        created_at = datetime.now(UTC)
        return cls(
            items=[
                _StoredDocument(
                    document=DocumentSummary(
                        id=uuid4(),
                        filename="sample.pdf",
                        contentType="application/pdf",
                        createdAt=created_at,
                        updatedAt=created_at,
                    ),
                    result=ParseResult(
                        schemaVersion="1.0",
                        markdown=(
                            "# Sample Document\n\nThis is seeded mock data for the documents API.\n"
                        ),
                        canonicalJson={
                            "document": {
                                "title": "Sample Document",
                                "sourceFilename": "sample.pdf",
                            },
                            "pages": [
                                {
                                    "pageNumber": 1,
                                    "blocks": [
                                        {
                                            "type": "paragraph",
                                            "text": (
                                                "This is seeded mock data for the documents API."
                                            ),
                                        }
                                    ],
                                }
                            ],
                        },
                    ),
                )
            ]
        )

    def list_documents(
        self,
        *,
        limit: int,
        offset: int,
        filename: str | None,
    ) -> DocumentListResponse:
        items = sorted(
            self._items.values(),
            key=lambda item: item.document.created_at,
            reverse=True,
        )
        if filename:
            lowered = filename.lower()
            items = [item for item in items if lowered in item.document.filename.lower()]
        total = len(items)
        paged_items = items[offset : offset + limit]
        return DocumentListResponse(
            items=[item.document for item in paged_items],
            total=total,
            limit=limit,
            offset=offset,
        )

    def get_document(self, document_id: UUID) -> DocumentResponse:
        item = self._items.get(document_id)
        if item is None:
            raise DocumentNotFoundError(document_id)
        return DocumentResponse(document=item.document)

    def get_document_result(self, document_id: UUID) -> DocumentParseResponse:
        item = self._items.get(document_id)
        if item is None:
            raise DocumentNotFoundError(document_id)
        return DocumentParseResponse(document=item.document, result=item.result)

    def create_document(
        self,
        *,
        filename: str,
        content_type: str,
    ) -> DocumentParseResponse:
        created_at = datetime.now(UTC)
        title = Path(filename).stem.replace("_", " ").replace("-", " ").strip() or "Mock Document"
        item = _StoredDocument(
            document=DocumentSummary(
                id=uuid4(),
                filename=filename,
                contentType=content_type,
                createdAt=created_at,
                updatedAt=created_at,
            ),
            result=ParseResult(
                schemaVersion="1.0",
                markdown=self._build_markdown(title=title, filename=filename),
                canonicalJson=self._build_canonical_json(title=title, filename=filename),
            ),
        )
        self._items[item.document.id] = item
        return DocumentParseResponse(document=item.document, result=item.result)

    def delete_document(self, document_id: UUID) -> None:
        deleted = self._items.pop(document_id, None)
        if deleted is None:
            raise DocumentNotFoundError(document_id)

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
