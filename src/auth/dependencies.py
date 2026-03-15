from fastapi import Depends, Request, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.auth.exceptions import ExpiredAccessTokenError, InvalidAccessTokenError, InvalidApiKeyError
from src.auth.models import UserModel
from src.auth.security import is_probable_api_key
from src.auth.service import AuthService
from src.common.errors import ApiError
from src.config import get_settings
from src.database import get_db_session

bearer_scheme = HTTPBearer(auto_error=False)
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False, scheme_name="ApiKeyAuth")


def get_auth_service(session: Session = Depends(get_db_session)) -> AuthService:
    settings = get_settings()
    return AuthService(
        session=session,
        secret_key=settings.auth_secret_key,
        access_token_ttl_seconds=settings.auth_access_token_ttl_seconds,
    )


def get_current_user(
    request: Request,
    _: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    service: AuthService = Depends(get_auth_service),
) -> UserModel:
    token = _extract_bearer_credential(request)
    if token is None:
        raise _unauthorized_error()

    try:
        return service.get_user_from_access_token(token)
    except ExpiredAccessTokenError as exc:
        raise ApiError(
            status_code=401,
            code="access_token_expired",
            message="Access token has expired.",
        ) from exc
    except InvalidAccessTokenError as exc:
        raise ApiError(
            status_code=401,
            code="invalid_access_token",
            message="Invalid access token.",
        ) from exc


def get_current_document_user(
    request: Request,
    _: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    __: str | None = Security(api_key_scheme),
    service: AuthService = Depends(get_auth_service),
) -> UserModel:
    api_key = _extract_api_key(request)
    if api_key is not None:
        return _authenticate_api_key(api_key=api_key, service=service)

    credential = _extract_bearer_credential(request)
    if credential is None:
        raise _unauthorized_error()

    if is_probable_api_key(credential):
        return _authenticate_api_key(api_key=credential, service=service)

    try:
        return service.get_user_from_access_token(credential)
    except ExpiredAccessTokenError as exc:
        raise ApiError(
            status_code=401,
            code="access_token_expired",
            message="Access token has expired.",
        ) from exc
    except InvalidAccessTokenError as exc:
        raise ApiError(
            status_code=401,
            code="invalid_access_token",
            message="Invalid access token.",
        ) from exc


def _authenticate_api_key(*, api_key: str, service: AuthService) -> UserModel:
    try:
        return service.get_user_from_api_key(api_key)
    except InvalidApiKeyError as exc:
        raise ApiError(
            status_code=401,
            code="invalid_api_key",
            message="Invalid API key.",
        ) from exc


def _extract_api_key(request: Request) -> str | None:
    raw_api_key = request.headers.get("X-API-Key")
    if raw_api_key is None:
        return None

    normalized = raw_api_key.strip()
    if not normalized:
        return None
    return normalized


def _extract_bearer_credential(request: Request) -> str | None:
    authorization = request.headers.get("Authorization")
    if authorization is None:
        return None

    scheme, _, credentials = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None

    normalized = credentials.strip()
    if not normalized:
        return None
    return normalized


def _unauthorized_error() -> ApiError:
    return ApiError(
        status_code=401,
        code="unauthorized",
        message="Authentication is required.",
    )
