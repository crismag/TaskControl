"""Typed, validated application settings.

Settings are read from the environment and an optional ``.env`` file, validated once at
startup, and passed explicitly to the components that need them. Nothing resolves
settings at import time, and no business module reads ``os.environ`` directly — both are
required by ``development/engineering/standards/20_PYTHON_AND_APPLICATION_STANDARDS.md``
and by the import rules in ``11_DEPENDENCY_RULES.md``.
"""

from __future__ import annotations

import os
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic import ValidationError as PydanticValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from taskcontrol.common.errors import ConfigurationError

ENV_PREFIX = "TASKCONTROL_"


class Environment(StrEnum):
    """The deployment environment a process believes it is running in."""

    LOCAL = "local"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogFormat(StrEnum):
    """How log records are rendered."""

    JSON = "json"
    "Structured single-line JSON. The default, and the only format for production."

    TEXT = "text"
    "Human-readable. Convenient locally; loses field fidelity."


class Settings(BaseSettings):
    """Validated configuration for a TaskControl process.

    Every field is read from an environment variable prefixed ``TASKCONTROL_``. Values
    are validated once; a process that cannot build valid settings must fail to start
    rather than run on invented defaults.
    """

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
        frozen=True,
    )

    environment: Environment = Field(
        default=Environment.LOCAL,
        description="Deployment environment this process is running in.",
    )
    debug: bool = Field(
        default=False,
        description="Enables verbose diagnostics. Must never be enabled in production.",
    )

    log_level: str = Field(
        default="INFO",
        description="Root log level: DEBUG, INFO, WARNING, ERROR, or CRITICAL.",
    )
    log_format: LogFormat = Field(
        default=LogFormat.JSON,
        description="Log rendering format.",
    )

    data_dir: Path = Field(
        default=Path("./data"),
        description="Directory for the database and local artefacts. Created on init.",
    )
    database_url: str = Field(
        default="",
        description=(
            "SQLAlchemy database URL. Empty means a SQLite file inside data_dir, which "
            "is what a local installation wants. Set a postgresql+psycopg:// URL for "
            "server mode."
        ),
    )

    api_host: str = Field(default="127.0.0.1", description="Interface the API binds to.")
    api_port: int = Field(default=8000, ge=1, le=65535, description="Port the API binds to.")

    # Cron layout. Every path is configurable because distributions disagree about them,
    # and a wrong path must be a setting an operator can correct rather than a constant
    # they have to patch (ADR 0026).
    cron_command: str = Field(
        default="crontab",
        description="The crontab executable. The only supported way to change a user crontab.",
    )
    cron_user: str = Field(
        default="",
        description=(
            "Whose user crontab to manage. Empty means the invoking user's own, which "
            "needs no privilege. Naming another user does."
        ),
    )
    cron_system_crontab: Path = Field(
        default=Path("/etc/crontab"), description="The system crontab file."
    )
    cron_d_dir: Path = Field(
        default=Path("/etc/cron.d"), description="Directory for one-file-per-task cron entries."
    )
    run_parts_root: Path = Field(
        default=Path("/etc"),
        description=(
            "Directory containing the run-parts directories — cron.hourly, cron.daily, "
            "and their siblings."
        ),
    )
    taskctl_command: str = Field(
        default="taskctl",
        description=(
            "How a deployed cron artefact invokes TaskControl. Must be resolvable from "
            "cron's environment, which is far smaller than a login shell's — an absolute "
            "path is usually the right answer on a real host."
        ),
    )

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalise_log_level(cls, value: object) -> object:
        """Accept any casing for the log level and normalise it to upper case."""
        return value.upper() if isinstance(value, str) else value

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        """Reject a log level that the standard library would not understand."""
        permitted = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if value not in permitted:
            message = f"log_level must be one of {sorted(permitted)}, got {value!r}"
            raise ValueError(message)
        return value

    @field_validator("database_url")
    @classmethod
    def _validate_database_url(cls, value: str) -> str:
        """Reject a URL whose scheme TaskControl does not support.

        Failing at startup is far kinder than failing on the first query. The message
        names the scheme rather than echoing the URL, which may embed a password.
        """
        if not value:
            return value
        scheme = value.split("://", 1)[0].split("+", 1)[0]
        supported = {"sqlite", "postgresql"}
        if scheme not in supported:
            message = f"database_url scheme must be one of {sorted(supported)}, got {scheme!r}"
            raise ValueError(message)
        return value

    @property
    def is_production(self) -> bool:
        """Whether this process considers itself production."""
        return self.environment is Environment.PRODUCTION

    @property
    def database_backend(self) -> str:
        """The database backend name, safe to display.

        Only the scheme. A full URL may carry credentials and must never reach a log, a
        health response, or an error message.
        """
        if not self.database_url:
            return "sqlite"
        return self.database_url.split("://", 1)[0].split("+", 1)[0]

    def describe(self) -> dict[str, str | int | bool]:
        """Return a redaction-safe summary for logs and the health endpoint.

        Only non-sensitive fields are included. As secret-bearing settings are added in
        later waves they must be excluded here rather than added.

        Returns:
            A mapping of settings safe to display.
        """
        return {
            "environment": str(self.environment),
            "debug": self.debug,
            "log_level": self.log_level,
            "log_format": str(self.log_format),
            "api_host": self.api_host,
            "api_port": self.api_port,
            # The URL itself is excluded: a PostgreSQL URL routinely embeds a password.
            "database_backend": self.database_backend,
        }


def _unknown_environment_variables() -> list[str]:
    """Return prefixed environment variables that match no known setting.

    A mistyped variable that is silently ignored is the failure mode TaskControl exists
    to remove from scheduled operations, so it is treated as a configuration error rather
    than overlooked.

    Returns:
        Sorted names of unrecognised ``TASKCONTROL_*`` variables.
    """
    known = {f"{ENV_PREFIX}{name}".upper() for name in Settings.model_fields}
    return sorted(
        name
        for name in os.environ
        if name.upper().startswith(ENV_PREFIX) and name.upper() not in known
    )


def load_settings(**overrides: object) -> Settings:
    """Build and validate settings.

    Args:
        **overrides: Explicit values that take precedence over the environment. Intended
            for tests and for composition roots that already hold a value.

    Returns:
        Validated settings.

    Raises:
        ConfigurationError: If a prefixed environment variable is unrecognised, or if the
            environment does not produce a valid configuration. The message names the
            offending fields and never includes their values, which may be secret.
    """
    if unknown := _unknown_environment_variables():
        raise ConfigurationError(
            "Unrecognised TaskControl environment variables.",
            details={"unknown_variables": unknown, "env_prefix": ENV_PREFIX},
        )

    try:
        return Settings(**overrides)  # type: ignore[arg-type]
    except PydanticValidationError as exc:
        fields = sorted({str(error["loc"][0]) for error in exc.errors() if error["loc"]})
        raise ConfigurationError(
            "Invalid TaskControl configuration.",
            details={"invalid_fields": fields, "env_prefix": ENV_PREFIX},
        ) from exc


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return process-wide settings, building them on first use.

    Deliberately lazy: importing this module must not read the environment. Composition
    roots call this once and pass the result down.

    Returns:
        Validated settings, cached for the lifetime of the process.
    """
    return load_settings()
