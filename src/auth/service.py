import re
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.auth.exceptions import (
    InvalidAccessTokenError,
    InvalidCredentialsError,
    InvalidEmailFormatError,
    UserAlreadyExistsError,
)
from src.auth.models import UserModel
from src.auth.schemas import AuthTokenResponse, UserProfile
from src.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthService:
    def __init__(
        self,
        *,
        session: Session,
        secret_key: str,
        access_token_ttl_seconds: int,
    ) -> None:
        self.session = session
        self.secret_key = secret_key
        self.access_token_ttl_seconds = access_token_ttl_seconds

    def register(self, *, email: str, password: str) -> AuthTokenResponse:
        normalized_email = _normalize_email(email)
        if not _is_valid_email(normalized_email):
            raise InvalidEmailFormatError(normalized_email)

        existing = self.session.scalar(select(UserModel).where(UserModel.email == normalized_email))
        if existing is not None:
            raise UserAlreadyExistsError(normalized_email)

        user = UserModel(
            id=str(uuid4()),
            email=normalized_email,
            password_hash=hash_password(password),
        )
        self.session.add(user)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            if _is_email_unique_violation(exc):
                raise UserAlreadyExistsError(normalized_email) from exc
            raise
        self.session.refresh(user)

        return self._build_auth_token_response(user)

    def login(self, *, email: str, password: str) -> AuthTokenResponse:
        normalized_email = _normalize_email(email)
        if not _is_valid_email(normalized_email):
            raise InvalidCredentialsError

        user = self.session.scalar(select(UserModel).where(UserModel.email == normalized_email))
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError

        return self._build_auth_token_response(user)

    def get_user_from_access_token(self, token: str) -> UserModel:
        payload = decode_access_token(token=token, secret_key=self.secret_key)
        user = self.session.get(UserModel, payload.user_id)
        if user is None:
            raise InvalidAccessTokenError
        return user

    def to_user_profile(self, user: UserModel) -> UserProfile:
        return self._to_user_profile(user)

    def _build_auth_token_response(self, user: UserModel) -> AuthTokenResponse:
        access_token = create_access_token(
            user_id=user.id,
            email=user.email,
            secret_key=self.secret_key,
            expires_in_seconds=self.access_token_ttl_seconds,
        )
        return AuthTokenResponse(
            accessToken=access_token,
            tokenType="bearer",
            expiresIn=self.access_token_ttl_seconds,
            user=self._to_user_profile(user),
        )

    @staticmethod
    def _to_user_profile(user: UserModel) -> UserProfile:
        return UserProfile(
            id=UUID(user.id),
            email=user.email,
            createdAt=user.created_at,
            updatedAt=user.updated_at,
        )


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _is_valid_email(email: str) -> bool:
    return bool(EMAIL_PATTERN.fullmatch(email))


def _is_email_unique_violation(exc: IntegrityError) -> bool:
    orig_text = str(exc.orig).lower() if exc.orig is not None else ""
    statement_text = str(exc.statement).lower() if exc.statement is not None else ""
    message = f"{orig_text} {statement_text}"

    return any(
        token in message
        for token in (
            "ix_users_email",
            "users.email",
            "unique constraint",
            "duplicate key value",
            "unique violation",
        )
    )
