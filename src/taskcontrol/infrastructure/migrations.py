"""Running Alembic migrations from inside the application.

``taskctl init`` must work on a clean clone without the operator learning Alembic, so the
migration runner is a first-class part of the product rather than a developer script.

Alembic is driven programmatically with an explicit connection. That matters: passing the
connection means the migration runs against exactly the engine the application configured,
so it cannot be applied to the wrong database because of an environment variable.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine

from taskcontrol.common.errors import ConfigurationError, PermanentInfrastructureError
from taskcontrol.infrastructure.logging import get_logger

logger = get_logger(__name__)


def _repository_root() -> Path:
    """Return the directory holding ``migrations/``.

    Walks up from this module. Works from a source checkout; an installed distribution
    ships the migrations alongside the package.

    Returns:
        The directory containing ``migrations``.

    Raises:
        ConfigurationError: If the migrations directory cannot be located.
    """
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "migrations" / "env.py").is_file():
            return candidate
    raise ConfigurationError(
        "The migrations directory could not be located. TaskControl cannot create or "
        "upgrade its database.",
        details={"searched_from": str(Path(__file__).resolve())},
    )


def alembic_config(engine: Engine) -> Config:
    """Build an Alembic configuration bound to an engine.

    Args:
        engine: The engine migrations should run against.

    Returns:
        The configuration, with the live connection attached.
    """
    root = _repository_root()
    config = Config()
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
    return config


def current_revision(engine: Engine) -> str | None:
    """Return the migration revision a database is currently at.

    Args:
        engine: The engine to inspect.

    Returns:
        The revision identifier, or ``None`` when no migration has been applied.
    """
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def head_revision(engine: Engine) -> str | None:
    """Return the newest revision this build knows about.

    Args:
        engine: Used only to locate the script directory.

    Returns:
        The head revision identifier.
    """
    return ScriptDirectory.from_config(alembic_config(engine)).get_current_head()


def is_up_to_date(engine: Engine) -> bool:
    """Whether a database is at the newest known revision.

    Used by readiness: a process serving requests against an out-of-date schema will fail
    in confusing ways, so it should report itself not ready instead.

    Args:
        engine: The engine to inspect.

    Returns:
        ``True`` when the database is at head.
    """
    return current_revision(engine) == head_revision(engine)


def upgrade_to_head(engine: Engine) -> str | None:
    """Apply every outstanding migration.

    Args:
        engine: The engine to migrate.

    Returns:
        The revision the database is at afterwards.

    Raises:
        PermanentInfrastructureError: If a migration fails. The message names the failure
            without exposing the database URL, which may embed a password.
    """
    config = alembic_config(engine)
    starting = current_revision(engine)

    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
    except Exception as exc:
        raise PermanentInfrastructureError(
            "Database migration failed. The database was left unchanged.",
            details={"from_revision": starting, "error": type(exc).__name__},
        ) from exc

    finished = current_revision(engine)
    logger.info(
        "Database migrated",
        extra={"from_revision": starting, "to_revision": finished},
    )
    return finished


def downgrade_to(engine: Engine, revision: str) -> str | None:
    """Reverse migrations down to a revision.

    Downgrades are destructive by nature. Exposed because migrations must be reversible to
    be testable, not because routine use is expected.

    Args:
        engine: The engine to migrate.
        revision: The target revision, or ``"base"`` for an empty schema.

    Returns:
        The revision the database is at afterwards.

    Raises:
        PermanentInfrastructureError: If the downgrade fails.
    """
    config = alembic_config(engine)
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, revision)
    except Exception as exc:
        raise PermanentInfrastructureError(
            "Database downgrade failed.",
            details={"target_revision": revision, "error": type(exc).__name__},
        ) from exc
    return current_revision(engine)
