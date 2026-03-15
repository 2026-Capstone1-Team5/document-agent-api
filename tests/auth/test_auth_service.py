from sqlalchemy.exc import IntegrityError

from src.auth.exceptions import UserAlreadyExistsError
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
