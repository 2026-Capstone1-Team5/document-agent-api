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
