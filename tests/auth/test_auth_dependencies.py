from types import SimpleNamespace
from typing import cast

import pytest
from starlette.requests import Request

from src.auth.dependencies import get_current_document_user
from src.auth.service import AuthService
from src.common.errors import ApiError


def _build_request(*, authorization: str | None = None, x_api_key: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if authorization is not None:
        headers.append((b"authorization", authorization.encode("latin-1")))
    if x_api_key is not None:
        headers.append((b"x-api-key", x_api_key.encode("latin-1")))

    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/documents",
            "headers": headers,
        }
    )


def test_current_document_user_prefers_bearer_token_over_x_api_key() -> None:
    jwt_user = SimpleNamespace(id="jwt-user")

    class FakeAuthService:
        def __init__(self) -> None:
            self.api_key_calls: list[str] = []

        def get_user_from_access_token(self, token: str):
            assert token == "jwt-token"
            return jwt_user

        def get_user_from_api_key(self, api_key: str):
            self.api_key_calls.append(api_key)
            raise AssertionError("X-API-Key should be ignored when a bearer JWT is present")

    service = FakeAuthService()
    request = _build_request(
        authorization="Bearer jwt-token",
        x_api_key="dagk_shadow_key",
    )

    current_user = get_current_document_user(
        request=request,
        _=None,
        __=None,
        service=cast(AuthService, service),
    )

    assert current_user is jwt_user
    assert service.api_key_calls == []


def test_current_document_user_rejects_conflicting_api_key_headers() -> None:
    class FakeAuthService:
        def get_user_from_access_token(self, token: str):
            raise AssertionError(f"unexpected JWT lookup: {token}")

        def get_user_from_api_key(self, api_key: str):
            raise AssertionError(f"unexpected API key lookup: {api_key}")

    request = _build_request(
        authorization="Bearer dagk_primary_key",
        x_api_key="dagk_secondary_key",
    )

    with pytest.raises(ApiError) as exc_info:
        get_current_document_user(
            request=request,
            _=None,
            __=None,
            service=cast(AuthService, FakeAuthService()),
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "unauthorized"
