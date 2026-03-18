from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import inspect

from src.auth.models import UserModel
from src.auth.security import hash_password
from src.documents.exceptions import DocumentNotFoundError, DocumentSourceUnavailableError
from src.documents.models import DocumentModel
from src.documents.service import DocumentService
from src.storage.backends import LocalObjectStorage


def test_file_data_is_deferred_by_default() -> None:
    mapper = inspect(DocumentModel)

    assert mapper.attrs.file_data.deferred is True


def _create_user(db_session, *, email: str = "owner@example.com") -> str:
    user = UserModel(
        id=str(uuid4()),
        email=email,
        password_hash=hash_password("password123!"),
    )
    db_session.add(user)
    db_session.commit()
    return user.id


def test_list_documents_is_empty_by_default(db_session, object_storage) -> None:
    service = DocumentService(session=db_session, storage=object_storage)
    owner_user_id = _create_user(db_session)

    result = service.list_documents(limit=20, offset=0, filename=None, owner_user_id=owner_user_id)

    assert result.total == 0
    assert len(result.items) == 0


def test_list_documents_filters_by_filename(db_session, object_storage) -> None:
    service = DocumentService(session=db_session, storage=object_storage)
    owner_user_id = _create_user(db_session)
    service.create_document(
        owner_user_id=owner_user_id,
        filename="invoice.pdf",
        content_type="application/pdf",
        file_data=b"invoice-bytes",
    )
    service.create_document(
        owner_user_id=owner_user_id,
        filename="report.pdf",
        content_type="application/pdf",
        file_data=b"report-bytes",
    )

    result = service.list_documents(
        limit=20,
        offset=0,
        filename="invoice",
        owner_user_id=owner_user_id,
    )

    assert result.total == 1
    assert result.items[0].filename == "invoice.pdf"


def test_create_document_returns_mock_payload(db_session, object_storage) -> None:
    service = DocumentService(session=db_session, storage=object_storage)
    owner_user_id = _create_user(db_session)
    file_bytes = b"%PDF-demo"

    created = service.create_document(
        owner_user_id=owner_user_id,
        filename="demo-file.pdf",
        content_type="application/pdf",
        file_data=file_bytes,
    )

    assert created.document.filename == "demo-file.pdf"
    assert created.document.content_type == "application/pdf"
    assert "demo file" in created.result.markdown.lower()

    stored = db_session.get(DocumentModel, str(created.document.id))
    assert stored is not None
    assert stored.file_data is None
    assert stored.source_object_key is not None


def test_get_document_raises_for_unknown_id(db_session, object_storage) -> None:
    service = DocumentService(session=db_session, storage=object_storage)
    owner_user_id = _create_user(db_session)

    with pytest.raises(DocumentNotFoundError):
        service.get_document(
            UUID("00000000-0000-0000-0000-000000000001"),
            owner_user_id=owner_user_id,
        )


def test_get_document_source_reads_payload_from_object_storage(db_session, object_storage) -> None:
    service = DocumentService(session=db_session, storage=object_storage)
    owner_user_id = _create_user(db_session)
    created = service.create_document(
        owner_user_id=owner_user_id,
        filename="source.pdf",
        content_type="application/pdf",
        file_data=b"source-bytes",
    )

    source = service.get_document_source(created.document.id, owner_user_id=owner_user_id)

    assert source.filename == "source.pdf"
    assert source.content_type == "application/pdf"
    assert source.data == b"source-bytes"


def test_get_document_source_uses_inline_fallback_when_object_backed_source_disappears(
    db_session,
) -> None:
    class SourceCleanupFailingStorage:
        def __init__(self) -> None:
            self.objects: dict[str, bytes] = {}
            self.put_count = 0

        def put_bytes(self, *, key: str, data: bytes, content_type: str) -> str:
            del content_type
            self.put_count += 1
            if self.put_count == 3:
                raise RuntimeError("failed to write canonical json")
            self.objects[key] = data
            return key

        def get_bytes(self, *, key: str) -> bytes:
            return self.objects[key]

        def delete_object(self, *, key: str) -> None:
            if "/source/" in key:
                raise RuntimeError("cleanup delete failed")
            self.objects.pop(key, None)

    storage = SourceCleanupFailingStorage()
    service = DocumentService(session=db_session, storage=storage)
    owner_user_id = _create_user(db_session)

    created = service.create_document(
        owner_user_id=owner_user_id,
        filename="source-fallback.pdf",
        content_type="application/pdf",
        file_data=b"source-fallback-bytes",
    )
    stored = db_session.get(DocumentModel, str(created.document.id))
    assert stored is not None
    assert stored.source_object_key is not None
    assert stored.file_data == b"source-fallback-bytes"

    storage.objects.pop(stored.source_object_key, None)

    source = service.get_document_source(created.document.id, owner_user_id=owner_user_id)
    assert source.data == b"source-fallback-bytes"


def test_get_document_source_raises_when_source_payload_is_unavailable(
    db_session,
    object_storage,
) -> None:
    service = DocumentService(session=db_session, storage=object_storage)
    owner_user_id = _create_user(db_session)
    created = service.create_document(
        owner_user_id=owner_user_id,
        filename="source-missing.pdf",
        content_type="application/pdf",
        file_data=b"source-missing-bytes",
    )
    stored = db_session.get(DocumentModel, str(created.document.id))
    assert stored is not None
    assert stored.source_object_key is not None

    object_storage._objects.pop(stored.source_object_key, None)  # noqa: SLF001

    with pytest.raises(DocumentSourceUnavailableError):
        service.get_document_source(created.document.id, owner_user_id=owner_user_id)


def test_delete_document_removes_created_document(db_session, object_storage) -> None:
    service = DocumentService(session=db_session, storage=object_storage)
    owner_user_id = _create_user(db_session)
    created = service.create_document(
        owner_user_id=owner_user_id,
        filename="delete-me.pdf",
        content_type="application/pdf",
        file_data=b"delete-me-bytes",
    )

    service.delete_document(created.document.id, owner_user_id=owner_user_id)

    with pytest.raises(DocumentNotFoundError):
        service.get_document(created.document.id, owner_user_id=owner_user_id)


def test_list_documents_only_returns_owner_items(db_session, object_storage) -> None:
    service = DocumentService(session=db_session, storage=object_storage)
    owner_user_id = _create_user(db_session, email="owner@example.com")
    other_user_id = _create_user(db_session, email="other@example.com")

    service.create_document(
        owner_user_id=owner_user_id,
        filename="owner.pdf",
        content_type="application/pdf",
        file_data=b"owner-bytes",
    )
    service.create_document(
        owner_user_id=other_user_id,
        filename="other.pdf",
        content_type="application/pdf",
        file_data=b"other-bytes",
    )

    result = service.list_documents(limit=20, offset=0, filename=None, owner_user_id=owner_user_id)

    assert result.total == 1
    assert result.items[0].filename == "owner.pdf"


def test_create_document_rolls_back_storage_on_write_failure(db_session) -> None:
    class FailingStorage:
        def __init__(self) -> None:
            self.objects: dict[str, bytes] = {}
            self.put_count = 0

        def put_bytes(self, *, key: str, data: bytes, content_type: str) -> str:
            del content_type
            self.put_count += 1
            if self.put_count == 3:
                raise RuntimeError("failed to write canonical json")
            self.objects[key] = data
            return key

        def get_bytes(self, *, key: str) -> bytes:
            return self.objects[key]

        def delete_object(self, *, key: str) -> None:
            self.objects.pop(key, None)

    storage = FailingStorage()
    service = DocumentService(session=db_session, storage=storage)
    owner_user_id = _create_user(db_session)

    with pytest.raises(RuntimeError, match="failed to write canonical json"):
        service.create_document(
            owner_user_id=owner_user_id,
            filename="rollback.pdf",
            content_type="application/pdf",
            file_data=b"rollback-bytes",
        )

    assert db_session.query(DocumentModel).count() == 0
    assert storage.objects == {}


def test_create_document_persists_fallback_when_cleanup_after_failure_is_incomplete(
    db_session,
) -> None:
    class CreateCleanupFailingStorage:
        def __init__(self) -> None:
            self.objects: dict[str, bytes] = {}
            self.put_count = 0

        def put_bytes(self, *, key: str, data: bytes, content_type: str) -> str:
            del content_type
            self.put_count += 1
            if self.put_count == 3:
                raise RuntimeError("failed to write canonical json")
            self.objects[key] = data
            return key

        def get_bytes(self, *, key: str) -> bytes:
            return self.objects[key]

        def delete_object(self, *, key: str) -> None:
            if "/source/" in key:
                raise RuntimeError("cleanup delete failed")
            self.objects.pop(key, None)

    storage = CreateCleanupFailingStorage()
    service = DocumentService(session=db_session, storage=storage)
    owner_user_id = _create_user(db_session)

    created = service.create_document(
        owner_user_id=owner_user_id,
        filename="cleanup-fail.pdf",
        content_type="application/pdf",
        file_data=b"cleanup-fail",
    )

    assert created.document.filename == "cleanup-fail.pdf"
    assert db_session.query(DocumentModel).count() == 1
    stored = db_session.get(DocumentModel, str(created.document.id))
    assert stored is not None
    assert stored.source_object_key in storage.objects
    assert stored.file_data == b"cleanup-fail"
    assert stored.result is not None
    assert stored.result.markdown == created.result.markdown
    assert stored.result.markdown_object_key is None


def test_create_document_persists_fallback_when_commit_and_cleanup_fail(db_session) -> None:
    class CommitFailOnceCleanupFailStorage:
        def __init__(self) -> None:
            self.objects: dict[str, bytes] = {}

        def put_bytes(self, *, key: str, data: bytes, content_type: str) -> str:
            del content_type
            self.objects[key] = data
            return key

        def get_bytes(self, *, key: str) -> bytes:
            return self.objects[key]

        def delete_object(self, *, key: str) -> None:
            if "/source/" in key:
                raise RuntimeError("cleanup delete failed")
            self.objects.pop(key, None)

    class CommitFailingSession:
        def __init__(self, wrapped_session) -> None:
            self.wrapped_session = wrapped_session
            self.fail_next_commit = True

        def __getattr__(self, name: str) -> Any:
            return getattr(self.wrapped_session, name)

        def commit(self) -> None:
            if self.fail_next_commit:
                self.fail_next_commit = False
                raise RuntimeError("forced commit failure")
            self.wrapped_session.commit()

        def rollback(self) -> None:
            self.wrapped_session.rollback()

    storage = CommitFailOnceCleanupFailStorage()
    owner_user_id = _create_user(db_session)
    service = DocumentService(
        session=cast(Any, CommitFailingSession(db_session)),
        storage=storage,
    )

    created = service.create_document(
        owner_user_id=owner_user_id,
        filename="commit-cleanup-fail.pdf",
        content_type="application/pdf",
        file_data=b"commit-cleanup-fail",
    )

    assert created.document.filename == "commit-cleanup-fail.pdf"
    persisted = DocumentService(session=db_session, storage=storage).get_document_result(
        created.document.id,
        owner_user_id=owner_user_id,
    )
    assert (
        persisted.result.canonical_json["document"]["sourceFilename"] == "commit-cleanup-fail.pdf"
    )


def test_get_document_result_uses_inline_fallback_when_object_backed_field_disappears(
    db_session,
) -> None:
    class MarkdownCleanupFailingStorage:
        def __init__(self) -> None:
            self.objects: dict[str, bytes] = {}
            self.put_count = 0

        def put_bytes(self, *, key: str, data: bytes, content_type: str) -> str:
            del content_type
            self.put_count += 1
            if self.put_count == 3:
                raise RuntimeError("failed to write canonical json")
            self.objects[key] = data
            return key

        def get_bytes(self, *, key: str) -> bytes:
            return self.objects[key]

        def delete_object(self, *, key: str) -> None:
            if key.endswith("/result/result.md"):
                raise RuntimeError("cleanup delete failed")
            self.objects.pop(key, None)

    storage = MarkdownCleanupFailingStorage()
    service = DocumentService(session=db_session, storage=storage)
    owner_user_id = _create_user(db_session)

    created = service.create_document(
        owner_user_id=owner_user_id,
        filename="inline-fallback.pdf",
        content_type="application/pdf",
        file_data=b"inline-fallback",
    )
    stored = db_session.get(DocumentModel, str(created.document.id))
    assert stored is not None
    assert stored.result is not None
    assert stored.result.markdown_object_key is not None

    storage.objects.pop(stored.result.markdown_object_key, None)

    persisted = service.get_document_result(created.document.id, owner_user_id=owner_user_id)
    assert persisted.result.markdown == created.result.markdown


def test_delete_document_fails_when_storage_delete_fails(db_session) -> None:
    class DeleteFailingStorage:
        def __init__(self) -> None:
            self.objects: dict[str, bytes] = {}

        def put_bytes(self, *, key: str, data: bytes, content_type: str) -> str:
            del content_type
            self.objects[key] = data
            return key

        def get_bytes(self, *, key: str) -> bytes:
            return self.objects[key]

        def delete_object(self, *, key: str) -> None:
            raise RuntimeError(f"failed to delete {key}")

    storage = DeleteFailingStorage()
    service = DocumentService(session=db_session, storage=storage)
    owner_user_id = _create_user(db_session)
    created = service.create_document(
        owner_user_id=owner_user_id,
        filename="delete-failure.pdf",
        content_type="application/pdf",
        file_data=b"delete-failure",
    )

    with pytest.raises(RuntimeError, match="failed to delete"):
        service.delete_document(created.document.id, owner_user_id=owner_user_id)

    # DB row must remain when blob deletion fails.
    remaining = service.get_document(created.document.id, owner_user_id=owner_user_id)
    assert remaining.document.id == created.document.id


def test_delete_document_partial_blob_failure_does_not_corrupt_document(db_session) -> None:
    class PartialDeleteFailingStorage:
        def __init__(self) -> None:
            self.objects: dict[str, bytes] = {}
            self.delete_calls = 0

        def put_bytes(self, *, key: str, data: bytes, content_type: str) -> str:
            del content_type
            self.objects[key] = data
            return key

        def get_bytes(self, *, key: str) -> bytes:
            return self.objects[key]

        def delete_object(self, *, key: str) -> None:
            self.delete_calls += 1
            if self.delete_calls == 3:
                raise RuntimeError(f"failed to delete {key}")
            self.objects.pop(key, None)

    storage = PartialDeleteFailingStorage()
    service = DocumentService(session=db_session, storage=storage)
    owner_user_id = _create_user(db_session)
    created = service.create_document(
        owner_user_id=owner_user_id,
        filename="partial-delete.pdf",
        content_type="application/pdf",
        file_data=b"partial-delete",
    )

    with pytest.raises(RuntimeError, match="failed to delete"):
        service.delete_document(created.document.id, owner_user_id=owner_user_id)

    # Document and parse payload should still be readable after rollback.
    remaining = service.get_document(created.document.id, owner_user_id=owner_user_id)
    assert remaining.document.id == created.document.id
    result = service.get_document_result(created.document.id, owner_user_id=owner_user_id)
    assert result.result.canonical_json["document"]["sourceFilename"] == "partial-delete.pdf"


def test_delete_document_allows_pre_missing_blob(db_session, object_storage) -> None:
    service = DocumentService(session=db_session, storage=object_storage)
    owner_user_id = _create_user(db_session)
    created = service.create_document(
        owner_user_id=owner_user_id,
        filename="already-missing.pdf",
        content_type="application/pdf",
        file_data=b"already-missing",
    )
    stored = db_session.get(DocumentModel, str(created.document.id))
    assert stored is not None
    assert stored.result is not None

    # Simulate previously-corrupted object storage state.
    assert stored.result.markdown_object_key is not None
    object_storage._objects.pop(stored.result.markdown_object_key, None)  # noqa: SLF001

    service.delete_document(created.document.id, owner_user_id=owner_user_id)

    with pytest.raises(DocumentNotFoundError):
        service.get_document(created.document.id, owner_user_id=owner_user_id)


def test_delete_document_restores_blobs_when_commit_fails(db_session, object_storage) -> None:
    class CommitFailingSession:
        def __init__(self, wrapped_session) -> None:
            self.wrapped_session = wrapped_session
            self.fail_next_commit = True

        def scalars(self, *args, **kwargs):
            return self.wrapped_session.scalars(*args, **kwargs)

        def delete(self, *args, **kwargs):
            return self.wrapped_session.delete(*args, **kwargs)

        def commit(self) -> None:
            if self.fail_next_commit:
                self.fail_next_commit = False
                raise RuntimeError("forced commit failure")
            self.wrapped_session.commit()

        def rollback(self) -> None:
            self.wrapped_session.rollback()

    normal_service = DocumentService(session=db_session, storage=object_storage)
    owner_user_id = _create_user(db_session)
    created = normal_service.create_document(
        owner_user_id=owner_user_id,
        filename="commit-fail-delete.pdf",
        content_type="application/pdf",
        file_data=b"commit-fail-delete",
    )

    failing_service = DocumentService(
        session=cast(Any, CommitFailingSession(db_session)),
        storage=object_storage,
    )
    with pytest.raises(RuntimeError, match="forced commit failure"):
        failing_service.delete_document(created.document.id, owner_user_id=owner_user_id)

    # DB row and blob payloads should both remain readable after rollback.
    remaining = normal_service.get_document(created.document.id, owner_user_id=owner_user_id)
    assert remaining.document.id == created.document.id
    result = normal_service.get_document_result(created.document.id, owner_user_id=owner_user_id)
    assert result.result.canonical_json["document"]["sourceFilename"] == "commit-fail-delete.pdf"


def test_get_document_result_reads_payload_from_object_storage(db_session, object_storage) -> None:
    service = DocumentService(session=db_session, storage=object_storage)
    owner_user_id = _create_user(db_session)
    created = service.create_document(
        owner_user_id=owner_user_id,
        filename="result.pdf",
        content_type="application/pdf",
        file_data=b"result-bytes",
    )

    result = service.get_document_result(created.document.id, owner_user_id=owner_user_id)

    assert result.document.id == created.document.id
    assert "result" in result.result.markdown.lower()
    assert result.result.canonical_json["document"]["sourceFilename"] == "result.pdf"


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("report.pdf", "report.pdf"),
        ("../report.pdf", "report.pdf"),
        ("dir\\report.pdf", "report.pdf"),
        ("..", "uploaded.bin"),
        (".", "uploaded.bin"),
        ("folder/..", "uploaded.bin"),
        ("", "uploaded.bin"),
    ],
)
def test_sanitize_filename_neutralizes_path_components(filename: str, expected: str) -> None:
    assert DocumentService._sanitize_filename(filename) == expected


def test_create_document_with_dotdot_filename_uses_safe_key(db_session, tmp_path) -> None:
    storage = LocalObjectStorage(root=str(tmp_path))
    service = DocumentService(session=db_session, storage=storage)
    owner_user_id = _create_user(db_session)

    created = service.create_document(
        owner_user_id=owner_user_id,
        filename="..",
        content_type="application/pdf",
        file_data=b"dotdot-bytes",
    )

    stored = db_session.get(DocumentModel, str(created.document.id))
    assert stored is not None
    assert stored.source_object_key is not None
    assert stored.source_object_key.endswith("/uploaded.bin")
