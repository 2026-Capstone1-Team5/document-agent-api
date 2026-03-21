from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from src.auth.service import AuthService
from src.config import get_settings
from src.database import get_db_session
from src.documents.models import DocumentModel
from src.documents.service import DocumentService
from src.main import app
from src.queueing.backends import InMemoryParseJobQueue
from src.queueing.dependencies import get_parse_job_queue
from src.storage.dependencies import get_object_storage


@pytest.fixture
def parse_job_queue() -> InMemoryParseJobQueue:
    return InMemoryParseJobQueue()


@pytest.fixture
def client(db_session, object_storage, parse_job_queue) -> Generator[TestClient, None, None]:
    settings = get_settings()
    auth_service = AuthService(
        session=db_session,
        secret_key=settings.auth_secret_key,
        access_token_ttl_seconds=settings.auth_access_token_ttl_seconds,
    )
    auth_payload = auth_service.register(
        email="owner@example.com",
        password="password123!",
    )

    DocumentService(session=db_session, storage=object_storage).create_document(
        owner_user_id=str(auth_payload.user.id),
        filename="sample.pdf",
        content_type="application/pdf",
        file_data=b"seeded-bytes",
    )

    app.dependency_overrides[get_db_session] = lambda: db_session
    app.dependency_overrides[get_object_storage] = lambda: object_storage
    app.dependency_overrides[get_parse_job_queue] = lambda: parse_job_queue
    app.state.test_owner_user_id = str(auth_payload.user.id)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        test_client.headers.update({"Authorization": f"Bearer {auth_payload.access_token}"})
        yield test_client
    app.dependency_overrides.clear()
    if hasattr(app.state, "test_owner_user_id"):
        delattr(app.state, "test_owner_user_id")


def _seed_document(*, filename: str, content_type: str, file_data: bytes) -> str:
    db_session = app.dependency_overrides[get_db_session]()
    object_storage = app.dependency_overrides[get_object_storage]()
    owner_user_id = app.state.test_owner_user_id
    created = DocumentService(session=db_session, storage=object_storage).create_document(
        owner_user_id=owner_user_id,
        filename=filename,
        content_type=content_type,
        file_data=file_data,
    )
    return str(created.document.id)


def test_list_documents_returns_seeded_item(client: TestClient) -> None:
    response = client.get("/api/v1/documents")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["filename"] == "sample.pdf"


def test_create_document_returns_queued_job(
    client: TestClient,
    parse_job_queue: InMemoryParseJobQueue,
) -> None:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("demo.pdf", b"%PDF-mock", "application/pdf")},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["job"]["filename"] == "demo.pdf"
    assert body["job"]["status"] == "queued"
    assert body["job"]["documentId"] is None
    assert parse_job_queue.messages[0]["filename"] == "demo.pdf"


def test_create_document_does_not_create_document_row(client: TestClient) -> None:
    db_session = app.dependency_overrides[get_db_session]()
    before_count = db_session.query(DocumentModel).count()

    response = client.post(
        "/api/v1/documents",
        files={"file": ("demo.pdf", b"%PDF-mock", "application/pdf")},
    )

    after_count = db_session.query(DocumentModel).count()

    assert response.status_code == 202
    assert before_count == after_count


def test_get_parse_job_returns_created_job(client: TestClient) -> None:
    created = client.post(
        "/api/v1/documents",
        files={"file": ("demo.pdf", b"%PDF-mock", "application/pdf")},
    ).json()

    response = client.get(f"/api/v1/parse-jobs/{created['job']['id']}")

    assert response.status_code == 200
    assert response.json()["job"]["status"] == "queued"


def test_get_parse_job_returns_404_for_unknown_id(client: TestClient) -> None:
    response = client.get("/api/v1/parse-jobs/00000000-0000-0000-0000-000000000001")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "parse_job_not_found"


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
    document_id = _seed_document(
        filename="demo.pdf",
        content_type="application/pdf",
        file_data=b"%PDF-mock",
    )

    response = client.get(
        f"/api/v1/documents/{document_id}/download",
        params={"format": "xml"},
    )

    assert response.status_code == 406
    assert response.json()["error"]["code"] == "unsupported_download_format"


def test_document_source_returns_inline_bytes_by_default(client: TestClient) -> None:
    document_id = _seed_document(
        filename="source.pdf",
        content_type="application/pdf",
        file_data=b"%PDF-source",
    )

    response = client.get(f"/api/v1/documents/{document_id}/source")

    assert response.status_code == 200
    assert response.content == b"%PDF-source"
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("inline;")
    assert "filename*=UTF-8''source.pdf" in response.headers["content-disposition"]
    assert response.headers["x-content-type-options"] == "nosniff"


def test_document_source_uses_server_side_pdf_media_type_for_inline_preview(
    client: TestClient,
) -> None:
    document_id = _seed_document(
        filename="source.pdf",
        content_type="text/html",
        file_data=b"<html>not-a-pdf</html>",
    )

    response = client.get(f"/api/v1/documents/{document_id}/source")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("inline;")


def test_document_source_supports_attachment_disposition(client: TestClient) -> None:
    document_id = _seed_document(
        filename="source.pdf",
        content_type="application/pdf",
        file_data=b"%PDF-source",
    )

    response = client.get(
        f"/api/v1/documents/{document_id}/source",
        params={"disposition": "attachment"},
    )

    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("attachment;")


def test_document_source_forces_attachment_for_unsafe_inline_media_type(
    client: TestClient,
) -> None:
    document_id = _seed_document(
        filename="vector",
        content_type="image/svg+xml",
        file_data=b"<svg></svg>",
    )

    response = client.get(f"/api/v1/documents/{document_id}/source")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-disposition"].startswith("attachment;")


def test_document_source_returns_500_when_source_payload_is_unavailable(
    client: TestClient,
) -> None:
    db_session = app.dependency_overrides[get_db_session]()
    object_storage = app.dependency_overrides[get_object_storage]()
    document_id = _seed_document(
        filename="source.pdf",
        content_type="application/pdf",
        file_data=b"%PDF-source",
    )
    stored = db_session.get(DocumentModel, document_id)
    assert stored is not None
    assert stored.source_object_key is not None

    object_storage._objects.pop(stored.source_object_key, None)  # noqa: SLF001

    response = client.get(f"/api/v1/documents/{document_id}/source")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "source_file_unavailable"


def test_unknown_document_returns_structured_404(client: TestClient) -> None:
    response = client.get("/api/v1/documents/00000000-0000-0000-0000-000000000001")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"


def test_documents_requires_auth_header(db_session, object_storage) -> None:
    app.dependency_overrides[get_db_session] = lambda: db_session
    app.dependency_overrides[get_object_storage] = lambda: object_storage
    app.dependency_overrides[get_parse_job_queue] = lambda: InMemoryParseJobQueue()
    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/api/v1/documents")
    app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_documents_accept_x_api_key(client: TestClient) -> None:
    issue_response = client.post(
        "/api/v1/auth/api-keys",
        json={"name": "MCP"},
    )
    assert issue_response.status_code == 201

    with TestClient(app, raise_server_exceptions=False) as api_key_client:
        response = api_key_client.get(
            "/api/v1/documents",
            headers={"X-API-Key": issue_response.json()["apiKey"]},
        )

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_documents_accept_api_key_in_bearer_header(client: TestClient) -> None:
    issue_response = client.post(
        "/api/v1/auth/api-keys",
        json={"name": "MCP"},
    )
    assert issue_response.status_code == 201

    response = client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {issue_response.json()['apiKey']}"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_documents_reject_invalid_api_key(db_session, object_storage) -> None:
    app.dependency_overrides[get_db_session] = lambda: db_session
    app.dependency_overrides[get_object_storage] = lambda: object_storage
    app.dependency_overrides[get_parse_job_queue] = lambda: InMemoryParseJobQueue()
    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get(
            "/api/v1/documents",
            headers={"X-API-Key": "dagk_invalid"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"
