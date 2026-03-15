from uuid import UUID

from fastapi import APIRouter, Depends, Response

from src.auth.dependencies import get_auth_service, get_current_user
from src.auth.exceptions import (
    ApiKeyNameAlreadyExistsError,
    ApiKeyNotFoundError,
    InvalidApiKeyNameError,
    InvalidCredentialsError,
    InvalidEmailFormatError,
    UserAlreadyExistsError,
)
from src.auth.models import UserModel
from src.auth.schemas import (
    ApiKeyListResponse,
    ApiKeyResponse,
    AuthTokenResponse,
    CreateApiKeyRequest,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from src.auth.service import AuthService
from src.common.errors import ApiError

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=AuthTokenResponse, status_code=201)
def register(
    request: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
) -> AuthTokenResponse:
    try:
        return service.register(email=request.email, password=request.password)
    except InvalidEmailFormatError as exc:
        raise ApiError(
            status_code=400,
            code="invalid_email_format",
            message=str(exc),
            details={"email": request.email},
        ) from exc
    except UserAlreadyExistsError as exc:
        raise ApiError(
            status_code=409,
            code="email_already_exists",
            message="Email is already registered.",
            details={"email": exc.email},
        ) from exc


@router.post("/login", response_model=AuthTokenResponse)
def login(
    request: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> AuthTokenResponse:
    try:
        return service.login(email=request.email, password=request.password)
    except InvalidCredentialsError as exc:
        raise ApiError(
            status_code=401,
            code="invalid_credentials",
            message="Invalid email or password.",
        ) from exc


@router.get("/me", response_model=UserResponse)
def me(
    current_user: UserModel = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    return UserResponse(user=service.to_user_profile(current_user))


@router.get("/api-keys", response_model=ApiKeyListResponse)
def list_api_keys(
    current_user: UserModel = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> ApiKeyListResponse:
    return service.list_api_keys(user=current_user)


@router.post("/api-keys", response_model=ApiKeyResponse, status_code=201)
def issue_api_key(
    request: CreateApiKeyRequest,
    current_user: UserModel = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> ApiKeyResponse:
    try:
        return service.issue_api_key(user=current_user, request=request)
    except InvalidApiKeyNameError as exc:
        raise ApiError(
            status_code=400,
            code="invalid_api_key_name",
            message="API key name must not be empty.",
        ) from exc
    except ApiKeyNameAlreadyExistsError as exc:
        raise ApiError(
            status_code=409,
            code="api_key_name_already_exists",
            message="API key name is already in use.",
            details={"name": exc.name},
        ) from exc


@router.delete("/api-keys/{api_key_id}", status_code=204)
def revoke_api_key(
    api_key_id: UUID,
    current_user: UserModel = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> Response:
    try:
        service.revoke_api_key(user=current_user, api_key_id=api_key_id)
    except ApiKeyNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code="api_key_not_found",
            message="API key not found.",
            details={"apiKeyId": exc.api_key_id},
        ) from exc
    else:
        return Response(status_code=204)
