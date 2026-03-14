from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_healthz() -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "document-agent-api",
        "version": "0.1.0",
    }


def test_cors_preflight_allows_web_origin() -> None:
    response = client.options(
        "/api/v1/documents",
        headers={
            "Origin": "https://document-agent-web.vercel.app",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "https://document-agent-web.vercel.app"
    )
