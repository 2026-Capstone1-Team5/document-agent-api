from uuid import UUID

import pytest
from sqlalchemy import inspect

from src.documents.exceptions import DocumentNotFoundError
from src.documents.models import DocumentModel
from src.documents.service import DocumentService


def test_file_data_is_deferred_by_default() -> None:
    mapper = inspect(DocumentModel)

    assert mapper.attrs.file_data.deferred is True


def test_list_documents_is_empty_by_default(db_session) -> None:
    service = DocumentService(session=db_session)

    result = service.list_documents(limit=20, offset=0, filename=None)

    assert result.total == 0
    assert len(result.items) == 0


def test_list_documents_filters_by_filename(db_session) -> None:
    service = DocumentService(session=db_session)
    service.create_document(
        filename="invoice.pdf",
        content_type="application/pdf",
        file_data=b"invoice-bytes",
    )
    service.create_document(
        filename="report.pdf",
        content_type="application/pdf",
        file_data=b"report-bytes",
    )

    result = service.list_documents(limit=20, offset=0, filename="invoice")

    assert result.total == 1
    assert result.items[0].filename == "invoice.pdf"


def test_create_document_returns_mock_payload(db_session) -> None:
    service = DocumentService(session=db_session)
    file_bytes = b"%PDF-demo"

    created = service.create_document(
        filename="demo-file.pdf",
        content_type="application/pdf",
        file_data=file_bytes,
    )

    assert created.document.filename == "demo-file.pdf"
    assert created.document.content_type == "application/pdf"
    assert "demo file" in created.result.markdown.lower()

    stored = db_session.get(DocumentModel, str(created.document.id))
    assert stored is not None
    assert stored.file_data == file_bytes


def test_get_document_raises_for_unknown_id(db_session) -> None:
    service = DocumentService(session=db_session)

    with pytest.raises(DocumentNotFoundError):
        service.get_document(UUID("00000000-0000-0000-0000-000000000001"))


def test_delete_document_removes_created_document(db_session) -> None:
    service = DocumentService(session=db_session)
    created = service.create_document(
        filename="delete-me.pdf",
        content_type="application/pdf",
        file_data=b"delete-me-bytes",
    )

    service.delete_document(created.document.id)

    with pytest.raises(DocumentNotFoundError):
        service.get_document(created.document.id)
