from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.auth.exceptions import ExpiredAccessTokenError, InvalidAccessTokenError
from src.auth.models import UserModel
from src.auth.service import AuthService
from src.common.errors import ApiError
from src.config import get_settings
from src.database import get_db_session

bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_service(session: Session = Depends(get_db_session)) -> AuthService:
    settings = get_settings()
    return AuthService(
        session=session,
        secret_key=settings.auth_secret_key,
        access_token_ttl_seconds=settings.auth_access_token_ttl_seconds,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    service: AuthService = Depends(get_auth_service),
) -> UserModel:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(
            status_code=401,
            code="unauthorized",
            message="Authentication is required.",
        )

    token = credentials.credentials.strip()
    if not token:
        raise ApiError(
            status_code=401,
            code="unauthorized",
            message="Authentication is required.",
        )

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
