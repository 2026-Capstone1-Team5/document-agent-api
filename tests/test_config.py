import pytest
from pydantic import ValidationError

from src.config import Settings


def test_r2_whitespace_values_are_treated_as_missing() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            auth_secret_key="secret",
            storage_backend="r2",
            storage_bucket="   ",
            storage_r2_endpoint="   ",
            storage_r2_access_key_id="   ",
            storage_r2_secret_access_key="   ",
        )

    message = str(exc_info.value)
    assert "Missing required R2 settings" in message
    assert "storage_bucket" in message
    assert "storage_r2_endpoint" in message
    assert "storage_r2_access_key_id" in message
    assert "storage_r2_secret_access_key" in message


def test_storage_r2_region_rejects_whitespace() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(auth_secret_key="secret", storage_r2_region="   ")

    assert "storage_r2_region must not be empty" in str(exc_info.value)


def test_queue_backend_rejects_unknown_value() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(auth_secret_key="secret", queue_backend="rabbitmq")

    assert "queue_backend must be one of" in str(exc_info.value)


def test_parse_job_queue_name_rejects_whitespace() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(auth_secret_key="secret", parse_job_queue_name="   ")

    assert "queue settings must not be empty" in str(exc_info.value)


def test_blank_redis_url_is_allowed_for_memory_queue() -> None:
    settings = Settings(
        auth_secret_key="secret",
        queue_backend="memory",
        redis_url="   ",
    )

    assert settings.queue_backend == "memory"
    assert settings.redis_url == ""


def test_blank_redis_url_is_rejected_for_redis_queue() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            auth_secret_key="secret",
            queue_backend="redis",
            redis_url="   ",
        )

    assert "redis_url is required when queue_backend=redis" in str(exc_info.value)
def test_pdftotext_command_rejects_whitespace() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(auth_secret_key="secret", pdftotext_command="   ")

    assert "pdftotext_command must not be empty" in str(exc_info.value)
