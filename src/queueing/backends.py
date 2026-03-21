from __future__ import annotations

import json
import logging
import socket
import ssl
from typing import Any, Protocol
from urllib.parse import unquote, urlparse

logger = logging.getLogger(__name__)


class ParseJobQueue(Protocol):
    def enqueue_parse_job(self, *, payload: dict[str, Any]) -> None: ...

    def dequeue_parse_job(self, *, timeout_seconds: int) -> dict[str, Any] | None: ...


class InMemoryParseJobQueue:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    def enqueue_parse_job(self, *, payload: dict[str, Any]) -> None:
        self.messages.append(payload)

    def dequeue_parse_job(self, *, timeout_seconds: int) -> dict[str, Any] | None:
        del timeout_seconds
        if not self.messages:
            return None
        return self.messages.pop(0)


class RedisParseJobQueue:
    def __init__(self, *, redis_url: str, queue_name: str) -> None:
        self.redis_url = redis_url
        self.queue_name = queue_name

    def enqueue_parse_job(self, *, payload: dict[str, Any]) -> None:
        serialized = json.dumps(payload, ensure_ascii=False)
        self._send_command("RPUSH", self.queue_name, serialized)

    def dequeue_parse_job(self, *, timeout_seconds: int) -> dict[str, Any] | None:
        response = self._send_command("BLPOP", self.queue_name, str(timeout_seconds))
        if response is None:
            return None
        if not isinstance(response, list) or len(response) != 2:
            msg = "unexpected BLPOP response from Redis"
            raise RuntimeError(msg)
        _, serialized = response
        if not isinstance(serialized, str):
            msg = "unexpected payload type from Redis queue"
            raise RuntimeError(msg)
        return json.loads(serialized)

    def _send_command(self, *parts: str) -> Any:
        parsed = urlparse(self.redis_url)
        if parsed.scheme not in {"redis", "rediss"}:
            msg = "redis_url must use redis:// or rediss://"
            raise ValueError(msg)

        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 6379
        username = unquote(parsed.username) if parsed.username else None
        password = unquote(parsed.password) if parsed.password else None
        database = parsed.path.lstrip("/") or "0"

        with socket.create_connection((host, port), timeout=5) as base_sock:
            sock: socket.socket
            if parsed.scheme == "rediss":
                context = ssl.create_default_context()
                sock = context.wrap_socket(base_sock, server_hostname=host)
            else:
                sock = base_sock
            stream = sock.makefile("rb")

            auth_parts = self._auth_parts(username=username, password=password)
            if auth_parts is not None:
                self._write_command(sock, *auth_parts)
                self._read_response(stream)
            if database != "0":
                self._write_command(sock, "SELECT", database)
                self._read_response(stream)

            self._write_command(sock, *parts)
            return self._read_response(stream)

    @staticmethod
    def _write_command(sock: socket.socket, *parts: str) -> None:
        chunks = [f"*{len(parts)}\r\n".encode("utf-8")]
        for part in parts:
            encoded = part.encode("utf-8")
            chunks.append(f"${len(encoded)}\r\n".encode("utf-8"))
            chunks.append(encoded + b"\r\n")
        sock.sendall(b"".join(chunks))

    @staticmethod
    def _read_response(stream) -> Any:  # type: ignore[no-untyped-def]
        line = stream.readline()
        if not line:
            msg = "connection closed while reading Redis response"
            raise RuntimeError(msg)

        prefix = line[:1]
        payload = line[1:-2]
        if prefix == b"+":
            return payload.decode("utf-8")
        if prefix == b"-":
            msg = payload.decode("utf-8", errors="replace")
            raise RuntimeError(msg)
        if prefix == b":":
            return int(payload)
        if prefix == b"$":
            length = int(payload)
            if length == -1:
                return None
            data = stream.read(length)
            stream.read(2)
            return data.decode("utf-8")
        if prefix == b"*":
            count = int(payload)
            if count == -1:
                return None
            return [RedisParseJobQueue._read_response(stream) for _ in range(count)]

        msg = "unsupported Redis RESP response"
        raise RuntimeError(msg)

    @staticmethod
    def _auth_parts(*, username: str | None, password: str | None) -> tuple[str, ...] | None:
        if not password:
            return None
        if username:
            return ("AUTH", username, password)
        return ("AUTH", password)


class LoggingParseJobQueue:
    def enqueue_parse_job(self, *, payload: dict[str, Any]) -> None:
        logger.info("queued parse job payload=%s", payload)

    def dequeue_parse_job(self, *, timeout_seconds: int) -> dict[str, Any] | None:
        del timeout_seconds
        return None
