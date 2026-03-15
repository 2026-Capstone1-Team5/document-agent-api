import pytest

from src.storage.backends import LocalObjectStorage


def test_local_object_storage_put_and_get(tmp_path) -> None:
    storage = LocalObjectStorage(root=str(tmp_path))

    key = "documents/demo/file.txt"
    storage.put_bytes(key=key, data=b"payload", content_type="text/plain")

    assert storage.get_bytes(key=key) == b"payload"


def test_local_object_storage_rejects_path_traversal(tmp_path) -> None:
    storage = LocalObjectStorage(root=str(tmp_path))

    with pytest.raises(ValueError, match="escapes storage root"):
        storage.put_bytes(
            key="../../../../outside.txt",
            data=b"payload",
            content_type="text/plain",
        )
