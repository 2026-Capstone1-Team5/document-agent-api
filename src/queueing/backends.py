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


class InMemoryParseJobQueue:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    def enqueue_parse_job(self, *, payload: dict[str, Any]) -> None:
        self.messages.append(payload)


class RedisParseJobQueue:
    def __init__(self, *, redis_url: str, queue_name: str) -> None:
        self.redis_url = redis_url
        self.queue_name = queue_name

    def enqueue_parse_job(self, *, payload: dict[str, Any]) -> None:
        serialized = json.dumps(payload, ensure_ascii=False)
        self._send_command("RPUSH", self.queue_name, serialized)

    def _send_command(self, *parts: str) -> None:
        parsed = urlparse(self.redis_url)
        if parsed.scheme not in {"redis", "rediss"}:
            msg = "redis_url must use redis:// or rediss://"
            raise ValueError(msg)

        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 6379
        password = unquote(parsed.password) if parsed.password else None
        database = parsed.path.lstrip("/") or "0"

        with socket.create_connection((host, port), timeout=5) as base_sock:
            sock: socket.socket
            if parsed.scheme == "rediss":
                context = ssl.create_default_context()
                sock = context.wrap_socket(base_sock, server_hostname=host)
            else:
                sock = base_sock

            if password:
                self._write_command(sock, "AUTH", password)
                self._read_response(sock)
            if database != "0":
                self._write_command(sock, "SELECT", database)
                self._read_response(sock)

            self._write_command(sock, *parts)
            self._read_response(sock)

    @staticmethod
    def _write_command(sock: socket.socket, *parts: str) -> None:
        chunks = [f"*{len(parts)}\r\n".encode("utf-8")]
        for part in parts:
            encoded = part.encode("utf-8")
            chunks.append(f"${len(encoded)}\r\n".encode("utf-8"))
            chunks.append(encoded + b"\r\n")
        sock.sendall(b"".join(chunks))

    @staticmethod
    def _read_response(sock: socket.socket) -> bytes:
        response = b""
        while not response.endswith(b"\r\n"):
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
        if response.startswith(b"-"):
            msg = response.decode("utf-8", errors="replace").strip()
            raise RuntimeError(msg)
        return response


class LoggingParseJobQueue:
    def enqueue_parse_job(self, *, payload: dict[str, Any]) -> None:
        logger.info("queued parse job payload=%s", payload)
