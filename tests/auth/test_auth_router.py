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


def test_api_key_list_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/auth/api-keys")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_api_key_list_is_empty_before_issue(client: TestClient) -> None:
    registered = _register(
        client,
        email="status@example.com",
        password="password123!",
    )

    response = client.get(
        "/api/v1/auth/api-keys",
        headers=_auth_headers(registered["accessToken"]),
    )

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_issue_api_key_returns_raw_key_and_list_entry(client: TestClient) -> None:
    registered = _register(
        client,
        email="issue@example.com",
        password="password123!",
    )

    issue_response = client.post(
        "/api/v1/auth/api-keys",
        headers=_auth_headers(registered["accessToken"]),
        json={"name": "Claude Desktop"},
    )

    assert issue_response.status_code == 201
    issued = issue_response.json()
    assert issued["apiKey"].startswith("dagk_")
    assert issued["key"]["name"] == "Claude Desktop"
    assert issued["key"]["prefix"] == issued["apiKey"][: len(issued["key"]["prefix"])]
    assert issued["key"]["createdAt"] is not None

    list_response = client.get(
        "/api/v1/auth/api-keys",
        headers=_auth_headers(registered["accessToken"]),
    )

    assert list_response.status_code == 200
    assert list_response.json() == {
        "items": [
            {
                "id": issued["key"]["id"],
                "name": "Claude Desktop",
                "prefix": issued["key"]["prefix"],
                "createdAt": issued["key"]["createdAt"],
            }
        ]
    }


def test_issue_api_key_allows_multiple_named_keys(client: TestClient) -> None:
    registered = _register(
        client,
        email="rotate@example.com",
        password="password123!",
    )

    first_response = client.post(
        "/api/v1/auth/api-keys",
        headers=_auth_headers(registered["accessToken"]),
        json={"name": "Codex"},
    )
    second_response = client.post(
        "/api/v1/auth/api-keys",
        headers=_auth_headers(registered["accessToken"]),
        json={"name": "Claude Code"},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert first_response.json()["apiKey"] != second_response.json()["apiKey"]
    assert first_response.json()["key"]["prefix"] != second_response.json()["key"]["prefix"]

    list_response = client.get(
        "/api/v1/auth/api-keys",
        headers=_auth_headers(registered["accessToken"]),
    )

    assert list_response.status_code == 200
    assert [item["name"] for item in list_response.json()["items"]] == ["Claude Code", "Codex"]


def test_issue_api_key_rejects_duplicate_name(client: TestClient) -> None:
    registered = _register(
        client,
        email="duplicate@example.com",
        password="password123!",
    )

    first_response = client.post(
        "/api/v1/auth/api-keys",
        headers=_auth_headers(registered["accessToken"]),
        json={"name": "MCP"},
    )
    duplicate_response = client.post(
        "/api/v1/auth/api-keys",
        headers=_auth_headers(registered["accessToken"]),
        json={"name": "MCP"},
    )

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["error"]["code"] == "api_key_name_already_exists"


def test_revoke_api_key_removes_only_target_key(client: TestClient) -> None:
    registered = _register(
        client,
        email="revoke@example.com",
        password="password123!",
    )

    first_issue_response = client.post(
        "/api/v1/auth/api-keys",
        headers=_auth_headers(registered["accessToken"]),
        json={"name": "Codex"},
    )
    second_issue_response = client.post(
        "/api/v1/auth/api-keys",
        headers=_auth_headers(registered["accessToken"]),
        json={"name": "Claude"},
    )
    assert first_issue_response.status_code == 201
    assert second_issue_response.status_code == 201

    revoke_response = client.delete(
        f"/api/v1/auth/api-keys/{first_issue_response.json()['key']['id']}",
        headers=_auth_headers(registered["accessToken"]),
    )
    assert revoke_response.status_code == 204

    list_response = client.get(
        "/api/v1/auth/api-keys",
        headers=_auth_headers(registered["accessToken"]),
    )

    assert list_response.status_code == 200
    assert list_response.json() == {
        "items": [
            {
                "id": second_issue_response.json()["key"]["id"],
                "name": "Claude",
                "prefix": second_issue_response.json()["key"]["prefix"],
                "createdAt": second_issue_response.json()["key"]["createdAt"],
            }
        ]
    }


def test_rename_api_key_updates_name_in_list(client: TestClient) -> None:
    registered = _register(
        client,
        email="rename@example.com",
        password="password123!",
    )

    issue_response = client.post(
        "/api/v1/auth/api-keys",
        headers=_auth_headers(registered["accessToken"]),
        json={"name": "Claude Desktop"},
    )
    assert issue_response.status_code == 201

    rename_response = client.patch(
        f"/api/v1/auth/api-keys/{issue_response.json()['key']['id']}",
        headers=_auth_headers(registered["accessToken"]),
        json={"name": "Claude Production"},
    )

    assert rename_response.status_code == 200
    assert rename_response.json() == {
        "id": issue_response.json()["key"]["id"],
        "name": "Claude Production",
        "prefix": issue_response.json()["key"]["prefix"],
        "createdAt": issue_response.json()["key"]["createdAt"],
    }

    list_response = client.get(
        "/api/v1/auth/api-keys",
        headers=_auth_headers(registered["accessToken"]),
    )

    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["name"] == "Claude Production"


def test_rename_api_key_rejects_duplicate_name(client: TestClient) -> None:
    registered = _register(
        client,
        email="rename-duplicate@example.com",
        password="password123!",
    )

    first_issue_response = client.post(
        "/api/v1/auth/api-keys",
        headers=_auth_headers(registered["accessToken"]),
        json={"name": "Codex"},
    )
    second_issue_response = client.post(
        "/api/v1/auth/api-keys",
        headers=_auth_headers(registered["accessToken"]),
        json={"name": "Claude"},
    )
    assert first_issue_response.status_code == 201
    assert second_issue_response.status_code == 201

    rename_response = client.patch(
        f"/api/v1/auth/api-keys/{second_issue_response.json()['key']['id']}",
        headers=_auth_headers(registered["accessToken"]),
        json={"name": "Codex"},
    )

    assert rename_response.status_code == 409
    assert rename_response.json()["error"]["code"] == "api_key_name_already_exists"


def test_rename_api_key_returns_404_for_missing_key(client: TestClient) -> None:
    registered = _register(
        client,
        email="rename-missing@example.com",
        password="password123!",
    )

    rename_response = client.patch(
        "/api/v1/auth/api-keys/00000000-0000-0000-0000-000000000001",
        headers=_auth_headers(registered["accessToken"]),
        json={"name": "Renamed"},
    )

    assert rename_response.status_code == 404
    assert rename_response.json()["error"]["code"] == "api_key_not_found"


@pytest.fixture
def client(db_session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db_session] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()
