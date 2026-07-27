"""Settings validation and redaction-safe description."""

from __future__ import annotations

from pathlib import Path

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
        "database_backend",
    }
    assert not any("secret" in key or "password" in key for key in described)
    assert "database_url" not in described, "a database URL may embed a password"


def test_settings_type_is_frozen_by_config() -> None:
    assert Settings.model_config["frozen"] is True


class TestMisprefixedVariables:
    """A plausible-but-wrong prefix must fail loudly, not be silently ignored.

    Strict validation that only guards the correct prefix guards nothing: the failure it
    exists to prevent is a variable that looks right, is wrong, and does nothing. This was
    found the hard way — two tests written during R2 used ``TC_DATABASE_URL`` and passed
    for the wrong reason, because the loader ignored it entirely.
    """

    def test_a_misprefixed_variable_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TC_DATABASE_URL", "sqlite+pysqlite:///x.db")

        with pytest.raises(ConfigurationError) as raised:
            load_settings()

        assert "TC_DATABASE_URL" in str(raised.value)

    def test_the_message_names_the_correct_variable(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """An operator must be able to fix it from the message alone."""
        monkeypatch.setenv("TC_DATA_DIR", str(tmp_path))

        with pytest.raises(ConfigurationError) as raised:
            load_settings()

        assert "TASKCONTROL_DATA_DIR" in str(raised.value)

    @pytest.mark.parametrize("prefix", ["TC_", "TASKCTL_", "TASK_CONTROL_"])
    def test_every_plausible_wrong_prefix_is_caught(
        self, prefix: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(f"{prefix}API_PORT", "9000")

        with pytest.raises(ConfigurationError):
            load_settings()

    def test_an_unrelated_variable_is_left_alone(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC_HOME belongs to something else and is none of TaskControl's business.

        Only a remainder that names a real setting is somebody meaning to configure this
        product; rejecting every unrelated variable in a process environment would make
        TaskControl unusable on a normal machine.
        """
        monkeypatch.setenv("TC_HOME", "/opt/somethingelse")
        monkeypatch.setenv("TCL_LIBRARY", "/usr/share/tcl")

        assert load_settings() is not None

    def test_the_secret_value_is_never_echoed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A misprefixed database URL routinely embeds a password."""
        monkeypatch.setenv("TC_DATABASE_URL", "postgresql+psycopg://user:hunter2@host/db")

        with pytest.raises(ConfigurationError) as raised:
            load_settings()

        assert "hunter2" not in str(raised.value)
        assert "hunter2" not in str(raised.value.details)
