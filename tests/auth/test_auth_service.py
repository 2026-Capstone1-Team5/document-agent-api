import pytest
from sqlalchemy.exc import IntegrityError

from src.auth.exceptions import InvalidApiKeyError, UserAlreadyExistsError
from src.auth.schemas import CreateApiKeyRequest
from src.auth.service import AuthService
from src.config import get_settings


def test_register_translates_commit_unique_race_to_user_already_exists(
    db_session,
    monkeypatch,
) -> None:
    settings = get_settings()
    service = AuthService(
        session=db_session,
        secret_key=settings.auth_secret_key,
        access_token_ttl_seconds=settings.auth_access_token_ttl_seconds,
    )

    original_commit = db_session.commit
    call_count = {"value": 0}

    def commit_with_duplicate_once() -> None:
        call_count["value"] += 1
        if call_count["value"] == 1:
            raise IntegrityError(
                "insert into users ...",
                {},
                Exception('duplicate key value violates unique constraint "ix_users_email"'),
            )
        original_commit()

    monkeypatch.setattr(db_session, "commit", commit_with_duplicate_once)

    try:
        service.register(email="race@example.com", password="password123!")
    except UserAlreadyExistsError:
        pass
    else:
        msg = "register should raise UserAlreadyExistsError on commit-time unique violation"
        raise AssertionError(msg)


def test_register_does_not_swallow_non_email_unique_violation(
    db_session,
    monkeypatch,
) -> None:
    settings = get_settings()
    service = AuthService(
        session=db_session,
        secret_key=settings.auth_secret_key,
        access_token_ttl_seconds=settings.auth_access_token_ttl_seconds,
    )

    def commit_with_non_email_unique_error() -> None:
        raise IntegrityError(
            "insert into users ...",
            {},
            Exception('duplicate key value violates unique constraint "ix_other_unique"'),
        )

    monkeypatch.setattr(db_session, "commit", commit_with_non_email_unique_error)

    try:
        service.register(email="race@example.com", password="password123!")
    except IntegrityError:
        pass
    else:
        msg = "register should re-raise non-email IntegrityError"
        raise AssertionError(msg)


def test_issue_api_key_can_lookup_user_list_keys_and_revoke_one(db_session) -> None:
    settings = get_settings()
    service = AuthService(
        session=db_session,
        secret_key=settings.auth_secret_key,
        access_token_ttl_seconds=settings.auth_access_token_ttl_seconds,
    )

    auth_payload = service.register(
        email="api-key@example.com",
        password="password123!",
    )
    user = service.get_user_from_access_token(auth_payload.access_token)

    first_issued = service.issue_api_key(
        user=user,
        request=CreateApiKeyRequest(name="Codex"),
    )
    second_issued = service.issue_api_key(
        user=user,
        request=CreateApiKeyRequest(name="Claude"),
    )
    looked_up_user = service.get_user_from_api_key(first_issued.api_key)
    listed = service.list_api_keys(user=user)

    assert first_issued.api_key.startswith("dagk_")
    assert first_issued.key.prefix == first_issued.api_key[: len(first_issued.key.prefix)]
    assert looked_up_user.id == str(auth_payload.user.id)
    assert [item.name for item in listed.items] == ["Claude", "Codex"]

    service.revoke_api_key(user=user, api_key_id=second_issued.key.id)

    listed_after_delete = service.list_api_keys(user=user)
    assert [item.name for item in listed_after_delete.items] == ["Codex"]

    with pytest.raises(InvalidApiKeyError):
        service.get_user_from_api_key(second_issued.api_key)
