"""Settings validation and redaction-safe description."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from taskcontrol.common.errors import ConfigurationError, ErrorCode
from taskcontrol.infrastructure.settings import (
    Environment,
    LogFormat,
    Settings,
    load_settings,
)


def test_defaults_are_local_and_safe() -> None:
    settings = load_settings()
    assert settings.environment is Environment.LOCAL
    assert settings.debug is False
    assert settings.log_format is LogFormat.JSON
    assert settings.api_host == "127.0.0.1", "must not default to a public interface"


def test_environment_variables_are_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TASKCONTROL_ENVIRONMENT", "production")
    monkeypatch.setenv("TASKCONTROL_API_PORT", "9001")
    settings = load_settings()
    assert settings.is_production
    assert settings.api_port == 9001


def test_log_level_is_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TASKCONTROL_LOG_LEVEL", "debug")
    assert load_settings().log_level == "DEBUG"


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("TASKCONTROL_LOG_LEVEL", "chatty"),
        ("TASKCONTROL_API_PORT", "0"),
        ("TASKCONTROL_API_PORT", "70000"),
        ("TASKCONTROL_ENVIRONMENT", "nowhere"),
    ],
)
def test_invalid_configuration_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    monkeypatch.setenv(variable, value)
    with pytest.raises(ConfigurationError) as caught:
        load_settings()
    assert caught.value.code is ErrorCode.CONFIGURATION_INVALID
    assert caught.value.details["invalid_fields"]


def test_configuration_error_never_reports_the_rejected_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rejected value may be a secret; the error names the field, not the value."""
    monkeypatch.setenv("TASKCONTROL_LOG_LEVEL", "sup3r-s3cret-value")
    with pytest.raises(ConfigurationError) as caught:
        load_settings()
    rendered = f"{caught.value.message} {caught.value.details}"
    assert "sup3r-s3cret-value" not in rendered


def test_unknown_settings_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A typo in an environment variable must fail loudly, not be silently ignored."""
    monkeypatch.setenv("TASKCONTROL_API_PORTT", "9000")
    with pytest.raises(ConfigurationError) as caught:
        load_settings()
    assert caught.value.details["unknown_variables"] == ["TASKCONTROL_API_PORTT"]


def test_unknown_variable_error_does_not_echo_the_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unrecognised variable may hold a secret, so only its name is reported."""
    monkeypatch.setenv("TASKCONTROL_DATABASE_PASSWORD", "s3cret-value-here")
    with pytest.raises(ConfigurationError) as caught:
        load_settings()
    assert "s3cret-value-here" not in f"{caught.value.message} {caught.value.details}"


def test_recognised_variables_are_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """The typo check must not reject a legitimate variable."""
    monkeypatch.setenv("TASKCONTROL_API_HOST", "0.0.0.0")  # noqa: S104
    assert load_settings().api_host == "0.0.0.0"  # noqa: S104


def test_settings_are_immutable() -> None:
    """Settings are frozen so no component can reconfigure the process at runtime."""
    settings = load_settings()
    with pytest.raises(PydanticValidationError):
        settings.api_port = 1234


def test_describe_excludes_nothing_sensitive_today_and_is_stable() -> None:
    described = load_settings().describe()
    assert set(described) == {
        "environment",
        "debug",
        "log_level",
        "log_format",
        "api_host",
        "api_port",
    }
    assert not any("secret" in key or "password" in key for key in described)


def test_settings_type_is_frozen_by_config() -> None:
    assert Settings.model_config["frozen"] is True
