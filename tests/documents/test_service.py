from uuid import UUID

import pytest

from src.documents.exceptions import DocumentNotFoundError
from src.documents.service import DocumentService


def test_seeded_service_lists_documents() -> None:
    service = DocumentService.seeded()

    result = service.list_documents(limit=20, offset=0, filename=None)

    assert result.total == 1
    assert len(result.items) == 1
    assert result.items[0].filename == "sample.pdf"


def test_list_documents_filters_by_filename() -> None:
    service = DocumentService.seeded()
    service.create_document(filename="invoice.pdf", content_type="application/pdf")
    service.create_document(filename="report.pdf", content_type="application/pdf")

    result = service.list_documents(limit=20, offset=0, filename="invoice")

    assert result.total == 1
    assert result.items[0].filename == "invoice.pdf"


def test_create_document_returns_mock_payload() -> None:
    service = DocumentService.seeded()

    created = service.create_document(
        filename="demo-file.pdf",
        content_type="application/pdf",
    )

    assert created.document.filename == "demo-file.pdf"
    assert created.document.content_type == "application/pdf"
    assert "demo file" in created.result.markdown.lower()


def test_get_document_raises_for_unknown_id() -> None:
    service = DocumentService.seeded()

    with pytest.raises(DocumentNotFoundError):
        service.get_document(UUID("00000000-0000-0000-0000-000000000001"))


def test_delete_document_removes_created_document() -> None:
    service = DocumentService.seeded()
    created = service.create_document(
        filename="delete-me.pdf",
        content_type="application/pdf",
    )

    service.delete_document(created.document.id)

    with pytest.raises(DocumentNotFoundError):
        service.get_document(created.document.id)
