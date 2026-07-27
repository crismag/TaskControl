"""Structured logging, correlation propagation, and secret redaction.

Redaction is the security-critical behaviour here, so it is tested through the real
handler rather than by calling the filter directly.
"""

from __future__ import annotations

import json

import pytest

from taskcontrol.infrastructure.logging import (
    REDACTED,
    configure_logging,
    correlation_context,
    get_correlation_context,
    get_logger,
    register_secret,
    uvicorn_log_config,
)
from taskcontrol.infrastructure.settings import LogFormat, load_settings


def test_structured_record_carries_expected_fields(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(load_settings(log_format=LogFormat.JSON))
    get_logger("taskcontrol.test").info("task created", extra={"task_id": "t-1"})

    record = json.loads(capsys.readouterr().err.strip())
    assert record["level"] == "INFO"
    assert record["logger"] == "taskcontrol.test"
    assert record["message"] == "task created"
    assert record["task_id"] == "t-1"
    assert "timestamp" in record


def test_correlation_context_is_merged_into_records(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(load_settings(log_format=LogFormat.JSON))
    with correlation_context(correlation_id="abc-123"):
        get_logger("taskcontrol.test").info("handling request")

    record = json.loads(capsys.readouterr().err.strip())
    assert record["correlation_id"] == "abc-123"


def test_nested_correlation_context_merges_rather_than_replaces() -> None:
    with correlation_context(correlation_id="req-1"):
        with correlation_context(execution_id="exec-9"):
            context = get_correlation_context()
            assert context == {"correlation_id": "req-1", "execution_id": "exec-9"}
        assert get_correlation_context() == {"correlation_id": "req-1"}
    assert get_correlation_context() == {}


def test_registered_secret_is_redacted_from_the_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(load_settings(log_format=LogFormat.JSON))
    register_secret("hunter2-super-secret")
    get_logger("taskcontrol.test").warning("connecting with hunter2-super-secret")

    rendered = capsys.readouterr().err
    assert "hunter2-super-secret" not in rendered
    assert REDACTED in rendered


def test_registered_secret_is_redacted_from_extra_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(load_settings(log_format=LogFormat.JSON))
    register_secret("prod-db-password-01")
    get_logger("taskcontrol.test").info(
        "resolved profile", extra={"dsn": "postgres://u:prod-db-password-01@host/db"}
    )

    assert "prod-db-password-01" not in capsys.readouterr().err


def test_sensitively_named_fields_are_redacted_by_key(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A field named like a secret is masked even when its value was never registered."""
    configure_logging(load_settings(log_format=LogFormat.JSON))
    get_logger("taskcontrol.test").info(
        "adapter configured",
        extra={"config": {"api_key": "never-registered", "host": "example.invalid"}},
    )

    record = json.loads(capsys.readouterr().err.strip())
    config = record["config"]
    assert isinstance(config, dict)
    assert config["api_key"] == REDACTED
    assert config["host"] == "example.invalid"


def test_short_values_are_not_registered_as_secrets(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Masking a short string would corrupt unrelated text without protecting anything."""
    configure_logging(load_settings(log_format=LogFormat.JSON))
    register_secret("abc")
    get_logger("taskcontrol.test").info("abcdefg is a normal word")

    assert "abcdefg" in capsys.readouterr().err


def test_text_format_appends_context(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(load_settings(log_format=LogFormat.TEXT))
    with correlation_context(correlation_id="xyz"):
        get_logger("taskcontrol.test").info("hello")

    rendered = capsys.readouterr().err
    assert "hello" in rendered
    assert "correlation_id=xyz" in rendered


def test_configure_logging_is_idempotent(capsys: pytest.CaptureFixture[str]) -> None:
    """Reconfiguring must replace the handler, never duplicate output."""
    settings = load_settings(log_format=LogFormat.JSON)
    configure_logging(settings)
    configure_logging(settings)
    configure_logging(settings)

    get_logger("taskcontrol.test").info("once")

    lines = [line for line in capsys.readouterr().err.splitlines() if line.strip()]
    assert len(lines) == 1


def test_exception_info_is_rendered(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(load_settings(log_format=LogFormat.JSON))
    try:
        raise ValueError("boom")
    except ValueError:
        get_logger("taskcontrol.test").exception("operation failed")

    record = json.loads(capsys.readouterr().err.strip())
    assert "ValueError: boom" in str(record["exception"])


class TestUvicornLogConfig:
    """Uvicorn's own loggers must not bypass TaskControl's handler.

    Uvicorn ships `propagate = False` and its own handlers, which produced a process that
    emitted JSON for application events and plain text for everything the server said.
    """

    def test_server_loggers_propagate_to_the_root_handler(self) -> None:
        config = uvicorn_log_config(load_settings())
        for name in ("uvicorn", "uvicorn.error"):
            assert config["loggers"][name]["propagate"] is True
            assert config["loggers"][name]["handlers"] == []

    def test_uvicorn_access_logger_is_silenced(self) -> None:
        """TaskControl emits its own access log from inside the correlation context."""
        config = uvicorn_log_config(load_settings())
        access = config["loggers"]["uvicorn.access"]
        assert access["propagate"] is False
        assert access["level"] == "CRITICAL"

    def test_existing_loggers_are_not_disabled(self) -> None:
        """Loggers created before uvicorn applies the config must keep working."""
        assert uvicorn_log_config(load_settings())["disable_existing_loggers"] is False

    def test_level_follows_settings(self) -> None:
        config = uvicorn_log_config(load_settings(log_level="WARNING"))
        assert config["loggers"]["uvicorn"]["level"] == "WARNING"
