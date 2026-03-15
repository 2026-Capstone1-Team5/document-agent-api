from typing import cast

from sqlalchemy.sql.schema import Table

from src.auth.models import UserApiKeyModel


def test_user_api_keys_metadata_includes_unique_name_per_user_index() -> None:
    table = cast(Table, UserApiKeyModel.__table__)
    composite_index = next(
        index for index in table.indexes if index.name == "ix_user_api_keys_user_id_name"
    )

    assert composite_index.unique is True
    assert [column.name for column in composite_index.columns] == ["user_id", "name"]


def test_user_api_keys_metadata_includes_unique_key_hash_index() -> None:
    table = cast(Table, UserApiKeyModel.__table__)
    key_hash_index = next(
        index for index in table.indexes if index.name == "ix_user_api_keys_key_hash"
    )

    assert key_hash_index.unique is True
    assert [column.name for column in key_hash_index.columns] == ["key_hash"]
