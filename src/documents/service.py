from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, load_only

from src.documents.exceptions import DocumentNotFoundError
from src.documents.models import DocumentModel, DocumentResultModel
from src.documents.schemas import (
    DocumentListResponse,
    DocumentParseResponse,
    DocumentResponse,
    DocumentSummary,
    ParseResult,
)


class DocumentService:
    def __init__(self, *, session: Session) -> None:
        self.session = session

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
                    DocumentModel.filename,
                    DocumentModel.content_type,
                    DocumentModel.created_at,
                    DocumentModel.updated_at,
                ),
                joinedload(DocumentModel.result).load_only(
                    DocumentResultModel.document_id,
                    DocumentResultModel.markdown,
                    DocumentResultModel.canonical_json,
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
        return self._to_document_parse_response(document)

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

        document = DocumentModel(
            id=document_id,
            owner_user_id=owner_user_id,
            filename=filename,
            content_type=content_type,
            file_data=file_data,
        )
        document.result = DocumentResultModel(
            document_id=document_id,
            markdown=self._build_markdown(title=title, filename=filename),
            canonical_json=self._build_canonical_json(title=title, filename=filename),
        )

        self.session.add(document)
        self.session.commit()
        self.session.refresh(document)
        self.session.refresh(document, attribute_names=["result"])

        return self._to_document_parse_response(document)

    def delete_document(self, document_id: UUID, *, owner_user_id: str) -> None:
        statement = select(DocumentModel).where(
            DocumentModel.id == str(document_id),
            DocumentModel.owner_user_id == owner_user_id,
        )
        document = self.session.scalars(statement).first()
        if document is None:
            raise DocumentNotFoundError(document_id)

        self.session.delete(document)
        self.session.commit()

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

    def _to_document_parse_response(self, document: DocumentModel) -> DocumentParseResponse:
        if document.result is None:
            raise DocumentNotFoundError(UUID(document.id))

        return DocumentParseResponse(
            document=self._to_document_summary(document),
            result=ParseResult(
                markdown=document.result.markdown,
                canonicalJson=document.result.canonical_json,
            ),
        )
