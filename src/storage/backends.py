from __future__ import annotations

from pathlib import Path
from typing import Protocol

import boto3
from botocore.client import Config


class ObjectStorage(Protocol):
    def put_bytes(self, *, key: str, data: bytes, content_type: str) -> str: ...

    def get_bytes(self, *, key: str) -> bytes: ...

    def delete_object(self, *, key: str) -> None: ...


class LocalObjectStorage:
    def __init__(self, *, root: str) -> None:
        self.root = Path(root).expanduser()
        self.root.mkdir(parents=True, exist_ok=True)
        self.root = self.root.resolve()

    def put_bytes(self, *, key: str, data: bytes, content_type: str) -> str:
        del content_type
        path = self._resolve_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def get_bytes(self, *, key: str) -> bytes:
        path = self._resolve_path(key)
        return path.read_bytes()

    def delete_object(self, *, key: str) -> None:
        path = self._resolve_path(key)
        if path.exists():
            path.unlink()

    def _resolve_path(self, key: str) -> Path:
        normalized_key = key.strip().lstrip("/")
        if not normalized_key:
            msg = "object key must not be empty"
            raise ValueError(msg)

        resolved_path = (self.root / normalized_key).resolve()
        try:
            resolved_path.relative_to(self.root)
        except ValueError as exc:
            msg = "object key escapes storage root"
            raise ValueError(msg) from exc
        return resolved_path


class R2ObjectStorage:
    def __init__(
        self,
        *,
        bucket: str,
        endpoint: str,
        access_key_id: str,
        secret_access_key: str,
        region: str,
    ) -> None:
        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
            config=Config(signature_version="s3v4"),
        )

    def put_bytes(self, *, key: str, data: bytes, content_type: str) -> str:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return key

    def get_bytes(self, *, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        body = response["Body"].read()
        return body if isinstance(body, bytes) else bytes(body)

    def delete_object(self, *, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)
