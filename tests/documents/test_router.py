from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from src.documents.dependencies import get_document_service
from src.documents.service import DocumentService
from src.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    service = DocumentService.seeded()
    app.dependency_overrides[get_document_service] = lambda: service
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_list_documents_returns_seeded_item(client: TestClient) -> None:
    response = client.get("/api/v1/documents")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["filename"] == "sample.pdf"


def test_create_document_returns_mock_result(client: TestClient) -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("demo.pdf", b"%PDF-mock", "application/pdf")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["document"]["filename"] == "demo.pdf"
    assert "canonicalJson" in body["result"]


def test_create_document_rejects_unsupported_type(client: TestClient) -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("demo.exe", b"abc", "application/octet-stream")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_create_document_returns_400_for_malformed_multipart(client: TestClient) -> None:
    response = client.post(
        "/api/v1/documents",
        files={"wrong": ("demo.pdf", b"%PDF-mock", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "malformed_multipart_request"


def test_document_download_rejects_unknown_format(client: TestClient) -> None:
    created = client.post(
        "/api/v1/documents",
        files={"file": ("demo.pdf", b"%PDF-mock", "application/pdf")},
    ).json()
    document_id = created["document"]["id"]

    response = client.get(
        f"/api/v1/documents/{document_id}/download",
        params={"format": "xml"},
    )

    assert response.status_code == 406
    assert response.json()["error"]["code"] == "unsupported_download_format"


def test_unknown_document_returns_structured_404(client: TestClient) -> None:
    response = client.get("/api/v1/documents/00000000-0000-0000-0000-000000000001")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"
