from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from src.database import get_db_session
from src.main import app


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _register(client: TestClient, *, email: str, password: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_register_returns_access_token(client: TestClient) -> None:
    body = _register(
        client,
        email="user@example.com",
        password="password123!",
    )

    assert body["tokenType"] == "bearer"
    assert body["expiresIn"] > 0
    assert body["user"]["email"] == "user@example.com"


def test_register_rejects_duplicate_email(client: TestClient) -> None:
    _register(
        client,
        email="dup@example.com",
        password="password123!",
    )

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "dup@example.com",
            "password": "password123!",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_already_exists"


def test_login_returns_access_token(client: TestClient) -> None:
    _register(
        client,
        email="login@example.com",
        password="password123!",
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "login@example.com",
            "password": "password123!",
        },
    )

    assert response.status_code == 200
    assert response.json()["tokenType"] == "bearer"


def test_login_rejects_invalid_credentials(client: TestClient) -> None:
    _register(
        client,
        email="invalid@example.com",
        password="password123!",
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "invalid@example.com",
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_me_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_me_returns_authenticated_user_profile(client: TestClient) -> None:
    registered = _register(
        client,
        email="me@example.com",
        password="password123!",
    )

    response = client.get(
        "/api/v1/auth/me",
        headers=_auth_headers(registered["accessToken"]),
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "me@example.com"


def test_me_rejects_invalid_token(client: TestClient) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers=_auth_headers("not-a-valid-token"),
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_access_token"


def test_register_rejects_invalid_email_format(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "invalid-email",
            "password": "password123!",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_email_format"


@pytest.fixture
def client(db_session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db_session] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()
