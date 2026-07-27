"""HTTP surface: health, readiness, correlation, error rendering, and OpenAPI."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from taskcontrol import __version__
from taskcontrol.api.middleware import CORRELATION_HEADER
from taskcontrol.apps.api.main import create_app
from taskcontrol.common.errors import NotFoundError, ValidationError
from taskcontrol.infrastructure.settings import Settings, load_settings

pytestmark = pytest.mark.integration


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


def test_health_reports_alive(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert body["environment"] == "local"


def test_ready_reports_each_dependency(client: TestClient) -> None:
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert [check["name"] for check in body["checks"]] == ["configuration"]


def test_liveness_and_readiness_are_separate_endpoints(client: TestClient) -> None:
    assert client.get("/api/v1/health").json() != client.get("/api/v1/ready").json()


def test_correlation_id_is_generated_when_absent(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.headers[CORRELATION_HEADER]


def test_correlation_id_supplied_by_the_client_is_honoured(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={CORRELATION_HEADER: "trace-42"})
    assert response.headers[CORRELATION_HEADER] == "trace-42"


def test_unknown_route_returns_404(client: TestClient) -> None:
    assert client.get("/api/v1/does-not-exist").status_code == 404


def test_openapi_document_is_generated(client: TestClient) -> None:
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    document = response.json()
    assert document["info"]["version"] == __version__
    assert "/api/v1/health" in document["paths"]
    assert "/api/v1/ready" in document["paths"]


def test_taskcontrol_errors_render_with_their_stable_code(settings: Settings) -> None:
    app = create_app(settings)

    @app.get("/api/v1/_test/not-found")
    async def _raise_not_found() -> None:
        raise NotFoundError("task not found", details={"task_id": "t-1"})

    with TestClient(app) as client:
        response = client.get("/api/v1/_test/not-found")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert error["message"] == "task not found"
    assert error["details"] == {"task_id": "t-1"}


def test_validation_errors_map_to_422(settings: Settings) -> None:
    app = create_app(settings)

    @app.get("/api/v1/_test/invalid")
    async def _raise_validation() -> None:
        raise ValidationError("cron expression is invalid")

    with TestClient(app) as client:
        response = client.get("/api/v1/_test/invalid")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"


def test_unhandled_exceptions_do_not_leak_internals(settings: Settings) -> None:
    app = create_app(settings)

    @app.get("/api/v1/_test/boom")
    async def _raise_unexpected() -> None:
        raise RuntimeError("internal detail that must not escape")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/_test/boom")

    assert response.status_code == 500
    rendered = response.text
    assert "internal detail that must not escape" not in rendered
    assert "Traceback" not in rendered
    assert response.json()["error"]["code"] == "permanent_infrastructure_failure"


def test_app_state_holds_the_settings_it_was_built_with() -> None:
    settings = load_settings(api_port=9999)
    app = create_app(settings)
    assert app.state.settings.api_port == 9999
