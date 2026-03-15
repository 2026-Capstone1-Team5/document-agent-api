import re
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.auth.exceptions import (
    ApiKeyNameAlreadyExistsError,
    ApiKeyNotFoundError,
    InvalidAccessTokenError,
    InvalidApiKeyError,
    InvalidApiKeyNameError,
    InvalidCredentialsError,
    InvalidEmailFormatError,
    UserAlreadyExistsError,
)
from src.auth.models import UserApiKeyModel, UserModel
from src.auth.schemas import (
    ApiKeyListResponse,
    ApiKeyResponse,
    ApiKeySummary,
    AuthTokenResponse,
    CreateApiKeyRequest,
    UpdateApiKeyRequest,
    UserProfile,
)
from src.auth.security import (
    create_access_token,
    create_api_key,
    decode_access_token,
    hash_api_key,
    hash_password,
    verify_password,
)
from src.database import utcnow

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

    def get_user_from_api_key(self, api_key: str) -> UserModel:
        api_key_hash = hash_api_key(api_key)
        statement = (
            select(UserModel)
            .join(UserApiKeyModel, UserApiKeyModel.user_id == UserModel.id)
            .where(UserApiKeyModel.key_hash == api_key_hash)
        )
        user = self.session.scalar(statement)
        if user is None:
            raise InvalidApiKeyError
        return user

    def list_api_keys(self, *, user: UserModel) -> ApiKeyListResponse:
        statement = (
            select(UserApiKeyModel)
            .where(UserApiKeyModel.user_id == user.id)
            .order_by(UserApiKeyModel.created_at.desc())
        )
        items = self.session.scalars(statement).all()
        return ApiKeyListResponse(items=[self._to_api_key_summary(item) for item in items])

    def issue_api_key(self, *, user: UserModel, request: CreateApiKeyRequest) -> ApiKeyResponse:
        normalized_name = _normalize_api_key_name(request.name)
        existing_name = self.session.scalar(
            select(UserApiKeyModel).where(
                UserApiKeyModel.user_id == user.id,
                UserApiKeyModel.name == normalized_name,
            )
        )
        if existing_name is not None:
            raise ApiKeyNameAlreadyExistsError(normalized_name)

        raw_api_key, api_key_prefix = create_api_key()
        api_key = UserApiKeyModel(
            id=str(uuid4()),
            user_id=user.id,
            name=normalized_name,
            key_hash=hash_api_key(raw_api_key),
            key_prefix=api_key_prefix,
            created_at=utcnow(),
        )
        self.session.add(api_key)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            if _is_api_key_name_unique_violation(exc):
                raise ApiKeyNameAlreadyExistsError(normalized_name) from exc
            raise
        self.session.refresh(api_key)
        return ApiKeyResponse(
            apiKey=raw_api_key,
            key=self._to_api_key_summary(api_key),
        )

    def revoke_api_key(self, *, user: UserModel, api_key_id: UUID) -> None:
        api_key = self.session.scalar(
            select(UserApiKeyModel).where(
                UserApiKeyModel.id == str(api_key_id),
                UserApiKeyModel.user_id == user.id,
            )
        )
        if api_key is None:
            raise ApiKeyNotFoundError(str(api_key_id))
        self.session.delete(api_key)
        self.session.commit()

    def rename_api_key(
        self,
        *,
        user: UserModel,
        api_key_id: UUID,
        request: UpdateApiKeyRequest,
    ) -> ApiKeySummary:
        api_key = self.session.scalar(
            select(UserApiKeyModel).where(
                UserApiKeyModel.id == str(api_key_id),
                UserApiKeyModel.user_id == user.id,
            )
        )
        if api_key is None:
            raise ApiKeyNotFoundError(str(api_key_id))

        normalized_name = _normalize_api_key_name(request.name)
        if api_key.name == normalized_name:
            return self._to_api_key_summary(api_key)

        existing_name = self.session.scalar(
            select(UserApiKeyModel).where(
                UserApiKeyModel.user_id == user.id,
                UserApiKeyModel.name == normalized_name,
                UserApiKeyModel.id != api_key.id,
            )
        )
        if existing_name is not None:
            raise ApiKeyNameAlreadyExistsError(normalized_name)

        api_key.name = normalized_name
        self.session.add(api_key)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            if _is_api_key_name_unique_violation(exc):
                raise ApiKeyNameAlreadyExistsError(normalized_name) from exc
            raise
        self.session.refresh(api_key)
        return self._to_api_key_summary(api_key)

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

    @staticmethod
    def _to_api_key_summary(api_key: UserApiKeyModel) -> ApiKeySummary:
        return ApiKeySummary(
            id=UUID(api_key.id),
            name=api_key.name,
            prefix=api_key.key_prefix,
            createdAt=api_key.created_at,
        )


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _is_valid_email(email: str) -> bool:
    return bool(EMAIL_PATTERN.fullmatch(email))


def _normalize_api_key_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise InvalidApiKeyNameError
    return normalized


def _is_email_unique_violation(exc: IntegrityError) -> bool:
    diag = getattr(exc.orig, "diag", None) if exc.orig is not None else None
    constraint_name = getattr(diag, "constraint_name", None)
    if isinstance(constraint_name, str):
        return constraint_name.lower() == "ix_users_email"

    orig_text = str(exc.orig).lower() if exc.orig is not None else ""
    statement_text = str(exc.statement).lower() if exc.statement is not None else ""
    message = f"{orig_text} {statement_text}"

    return any(
        token in message
        for token in (
            "ix_users_email",
            "users.email",
        )
    )


def _is_api_key_name_unique_violation(exc: IntegrityError) -> bool:
    diag = getattr(exc.orig, "diag", None) if exc.orig is not None else None
    constraint_name = getattr(diag, "constraint_name", None)
    if isinstance(constraint_name, str):
        return constraint_name.lower() == "ix_user_api_keys_user_id_name"

    orig_text = str(exc.orig).lower() if exc.orig is not None else ""
    statement_text = str(exc.statement).lower() if exc.statement is not None else ""
    message = f"{orig_text} {statement_text}"

    return any(
        token in message
        for token in (
            "ix_user_api_keys_user_id_name",
            "user_api_keys.user_id",
            "user_api_keys.name",
        )
    )
