from unittest.mock import MagicMock, patch

from src.queueing.backends import RedisParseJobQueue


def test_redis_auth_parts_supports_acl_username() -> None:
    parts = RedisParseJobQueue._auth_parts(username="default", password="secret")

    assert parts == ("AUTH", "default", "secret")


def test_redis_auth_parts_falls_back_to_password_only() -> None:
    parts = RedisParseJobQueue._auth_parts(username=None, password="secret")

    assert parts == ("AUTH", "secret")


def test_redis_auth_parts_returns_none_without_password() -> None:
    parts = RedisParseJobQueue._auth_parts(username="default", password=None)

    assert parts is None


def test_dequeue_parse_job_uses_blocking_read_timeout_grace() -> None:
    queue = RedisParseJobQueue(
        redis_url="redis://default:secret@localhost:6379/0",
        queue_name="parse-jobs",
    )
    connection = MagicMock()
    fake_socket = MagicMock()
    connection.__enter__.return_value = fake_socket
    connection.__exit__.return_value = None
    fake_stream = MagicMock()
    fake_socket.makefile.return_value = fake_stream

    with (
        patch("src.queueing.backends.socket.create_connection", return_value=connection),
        patch.object(
            RedisParseJobQueue,
            "_read_response",
            side_effect=["OK", ["parse-jobs", "{}"]],
        ),
    ):
        queue.dequeue_parse_job(timeout_seconds=5)

    fake_socket.settimeout.assert_called_with(10)
