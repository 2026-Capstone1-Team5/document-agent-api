from fastapi import APIRouter, Depends

from src.auth.dependencies import get_auth_service, get_current_user
from src.auth.exceptions import (
    InvalidCredentialsError,
    InvalidEmailFormatError,
    UserAlreadyExistsError,
)
from src.auth.models import UserModel
from src.auth.schemas import AuthTokenResponse, LoginRequest, RegisterRequest, UserResponse
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
