from __future__ import annotations

from fastapi.testclient import TestClient

from powershift import __version__
from powershift.core.config import Settings
from powershift.db.migrate import build_alembic_config, head_revision
from powershift.main import create_app


def test_health_reports_ok_version_and_latest_schema(
    client: TestClient, settings: Settings
) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert body["schema_revision"] == head_revision(build_alembic_config())
    assert body["database_path"] == str(settings.database_path)


def test_request_without_token_is_rejected(settings: Settings) -> None:
    with TestClient(create_app(settings)) as anonymous:
        response = anonymous.get("/api/health")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_request_with_wrong_token_is_rejected(settings: Settings) -> None:
    with TestClient(create_app(settings), headers={"X-PowerShift-Token": "wrong"}) as client:
        response = client.get("/api/health")

    assert response.status_code == 401


def test_unknown_route_returns_json_error_without_internals(client: TestClient) -> None:
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "message": "Not Found", "fields": {}}}


def test_cors_allows_tauri_origin_and_token_header(client: TestClient) -> None:
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://tauri.localhost",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-PowerShift-Token",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://tauri.localhost"


def test_cors_rejects_unknown_origin(client: TestClient) -> None:
    response = client.get("/api/health", headers={"Origin": "http://evil.example"})

    assert "access-control-allow-origin" not in response.headers


def test_docs_are_disabled_when_token_is_set(client: TestClient) -> None:
    # Interactive docs exist only in tokenless manual dev runs, never in the app.
    assert client.get("/docs").status_code == 404
