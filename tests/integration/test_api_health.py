"""HTTP surface: health, readiness, correlation, error rendering, and OpenAPI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from taskcontrol import __version__
from taskcontrol.api.middleware import CORRELATION_HEADER
from taskcontrol.apps.api.main import create_app
from taskcontrol.common.errors import NotFoundError, ValidationError
from taskcontrol.infrastructure.database import create_database_engine
from taskcontrol.infrastructure.logging import configure_logging, get_logger
from taskcontrol.infrastructure.migrations import upgrade_to_head
from taskcontrol.infrastructure.settings import Settings, load_settings

pytestmark = pytest.mark.integration


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


def test_liveness_does_not_depend_on_the_database(client: TestClient) -> None:
    """Liveness answers "is this process alive"; it must not touch a dependency."""
    assert client.get("/api/v1/health").status_code == 200


def test_health_reports_alive(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert body["environment"] == "local"


def test_ready_reports_each_dependency(client: TestClient) -> None:
    response = client.get("/api/v1/ready")
    body = response.json()
    assert [check["name"] for check in body["checks"]] == ["configuration", "database"]


def test_not_ready_without_a_schema(tmp_path: Path) -> None:
    """Serving against a missing schema fails confusingly, so say so instead."""
    url = f"sqlite+pysqlite:///{(tmp_path / 'empty.db').as_posix()}"
    with TestClient(create_app(load_settings(database_url=url))) as client:
        response = client.get("/api/v1/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["ready"] is False
    database = next(check for check in body["checks"] if check["name"] == "database")
    assert "taskctl init" in database["detail"]


def test_not_ready_when_the_database_is_unreachable(tmp_path: Path) -> None:
    """A missing directory is a different problem from a missing schema."""
    url = f"sqlite+pysqlite:///{(tmp_path / 'nope' / 'x.db').as_posix()}"
    with TestClient(create_app(load_settings(database_url=url))) as client:
        response = client.get("/api/v1/ready")

    assert response.status_code == 503
    database = next(check for check in response.json()["checks"] if check["name"] == "database")
    assert "not reachable" in database["detail"]


def test_ready_once_the_database_is_initialised(tmp_path: Path) -> None:
    """The positive case: an initialised database makes the process ready."""
    settings = load_settings(
        database_url=f"sqlite+pysqlite:///{(tmp_path / 'ready.db').as_posix()}"
    )
    engine = create_database_engine(settings.database_url)
    try:
        upgrade_to_head(engine)
    finally:
        engine.dispose()

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/ready")

    assert response.status_code == 200
    assert response.json()["ready"] is True


def test_readiness_never_reveals_the_database_url(tmp_path: Path) -> None:
    """A PostgreSQL URL routinely embeds a password."""
    secret_url = f"sqlite+pysqlite:///{(tmp_path / 'nonexistent' / 'x.db').as_posix()}"
    settings = load_settings(database_url=secret_url)

    with TestClient(create_app(settings)) as client:
        rendered = client.get("/api/v1/ready").text

    assert secret_url not in rendered


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


class TestAccessLog:
    """One structured, correlated access record per request.

    Uvicorn's access log is written after the response leaves the application, outside the
    correlation context, so it cannot carry the identifier that makes a request
    followable. TaskControl emits its own from the middleware instead.
    """

    def test_request_is_logged_with_correlation_and_timing(
        self, settings: Settings, capsys: pytest.CaptureFixture[str]
    ) -> None:
        configure_logging(settings)
        with TestClient(create_app(settings)) as client:
            client.get("/api/v1/health", headers={CORRELATION_HEADER: "trace-99"})

        record = _access_record(capsys.readouterr().err)
        assert record["correlation_id"] == "trace-99"
        assert record["http_method"] == "GET"
        assert record["path"] == "/api/v1/health"
        assert record["http_status"] == 200
        assert isinstance(record["duration_ms"], float)

    def test_client_errors_are_logged_at_warning(
        self, settings: Settings, capsys: pytest.CaptureFixture[str]
    ) -> None:
        configure_logging(settings)
        with TestClient(create_app(settings)) as client:
            client.get("/api/v1/nope")

        record = _access_record(capsys.readouterr().err)
        assert record["level"] == "WARNING"
        assert record["http_status"] == 404

    def test_server_errors_are_logged_at_error(
        self, settings: Settings, capsys: pytest.CaptureFixture[str]
    ) -> None:
        configure_logging(settings)
        app = create_app(settings)

        @app.get("/api/v1/_test/boom")
        async def _boom() -> None:
            raise RuntimeError("failure")

        with TestClient(app, raise_server_exceptions=False) as client:
            client.get("/api/v1/_test/boom")

        record = _access_record(capsys.readouterr().err)
        assert record["level"] == "ERROR"

    def test_application_log_and_access_log_share_the_correlation_id(
        self, settings: Settings, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The point of the exercise: one request is followable across both records."""
        configure_logging(settings)
        app = create_app(settings)

        @app.get("/api/v1/_test/logs")
        async def _emit() -> dict[str, str]:
            get_logger("taskcontrol.test").info("handler ran")
            return {"ok": "yes"}

        with TestClient(app) as client:
            client.get("/api/v1/_test/logs", headers={CORRELATION_HEADER: "shared-id"})

        records = [
            json.loads(line)
            for line in capsys.readouterr().err.splitlines()
            if line.strip().startswith("{")
        ]
        by_message = {record["message"]: record for record in records}
        assert by_message["handler ran"]["correlation_id"] == "shared-id"
        assert by_message["HTTP request"]["correlation_id"] == "shared-id"


def _access_record(stderr: str) -> dict[str, object]:
    """Return the single access-log record found in captured stderr."""
    records: list[dict[str, object]] = [
        json.loads(line)
        for line in stderr.splitlines()
        if line.strip().startswith("{") and "http_status" in line
    ]
    assert len(records) == 1, f"expected exactly one access record, got {len(records)}"
    return records[0]


def test_uvicorn_colour_duplicates_never_reach_a_sink(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    """`color_message` carries ANSI escapes and must be stripped from structured output."""
    configure_logging(settings)
    get_logger("uvicorn.error").info(
        "Started server process", extra={"color_message": "Started \x1b[36mprocess\x1b[0m"}
    )

    rendered = capsys.readouterr().err
    assert "color_message" not in rendered
    assert "\\u001b" not in rendered
