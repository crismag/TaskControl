"""Database engine and session construction.

SQLite works with no configuration; PostgreSQL works by changing one setting. Everything
that differs between them is confined to this module, so no repository, mapper, or use
case contains a backend conditional.

Two SQLite behaviours are corrected here rather than tolerated, because both would
otherwise show up as data loss in a scheduled-task product:

* **Foreign keys are off by default.** A `PRAGMA` enables them per connection.
* **The default journal serialises readers against a writer.** WAL mode lets the API read
  while the runtime writes.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from taskcontrol.common.errors import ConfigurationError
from taskcontrol.infrastructure.settings import Settings

SQLITE_MEMORY_URL = "sqlite+pysqlite:///:memory:"


def database_url(settings: Settings) -> str:
    """Return the database URL a process should use.

    Args:
        settings: Validated settings.

    Returns:
        An explicit ``database_url`` when set, otherwise a SQLite file inside the
        configured data directory.
    """
    if settings.database_url:
        return settings.database_url
    return f"sqlite+pysqlite:///{(settings.data_dir / 'taskcontrol.db').as_posix()}"


def is_sqlite(url: str) -> bool:
    """Whether a URL addresses SQLite."""
    return url.startswith("sqlite")


def create_database_engine(url: str, *, echo: bool = False) -> Engine:
    """Build a configured engine.

    Args:
        url: The database URL.
        echo: Emit SQL to the logger. Development only.

    Returns:
        The engine, with backend-appropriate pooling and pragmas applied.

    Raises:
        ConfigurationError: If the URL names a driver that is not installed.
    """
    options: dict[str, Any] = {"echo": echo, "future": True}

    if is_sqlite(url):
        # A file-backed SQLite database is shared between threads in this process; an
        # in-memory one must additionally share a single connection or each thread would
        # silently get its own empty database.
        options["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url:
            options["poolclass"] = StaticPool
    else:
        options["pool_pre_ping"] = True

    try:
        engine = create_engine(url, **options)
    except ModuleNotFoundError as exc:
        raise ConfigurationError(
            "The database driver for this URL is not installed.",
            details={"missing_module": exc.name or "unknown"},
        ) from exc

    if is_sqlite(url):
        _apply_sqlite_pragmas(engine)

    return engine


def _apply_sqlite_pragmas(engine: Engine) -> None:
    """Enable the SQLite behaviours TaskControl depends on.

    Args:
        engine: The engine to attach the listener to.
    """

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection: Any, _: Any) -> None:
        cursor = dbapi_connection.cursor()
        try:
            # Off by default in SQLite. Without this, a delete would orphan revisions.
            cursor.execute("PRAGMA foreign_keys=ON")
            # WAL lets readers proceed during a write. Not available for in-memory
            # databases, where it is silently ignored.
            cursor.execute("PRAGMA journal_mode=WAL")
            # Wait rather than failing immediately when another connection holds a write
            # lock: the API and the runtime will contend routinely.
            cursor.execute("PRAGMA busy_timeout=5000")
        finally:
            cursor.close()


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Build a session factory for an engine.

    ``expire_on_commit`` is off: repositories return domain objects, not ORM instances, so
    there is nothing to refresh after a commit and re-querying would be waste.

    Args:
        engine: The engine to bind to.

    Returns:
        The session factory.
    """
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def ensure_data_directory(settings: Settings) -> Path:
    """Create the data directory if it does not exist.

    Args:
        settings: Validated settings.

    Returns:
        The directory path.

    Raises:
        ConfigurationError: If the directory cannot be created.
    """
    try:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigurationError(
            "The configured data directory cannot be created.",
            details={"data_dir": str(settings.data_dir), "reason": exc.strerror},
        ) from exc
    return settings.data_dir


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Run a block inside a session that commits or rolls back.

    Prefer :class:`taskcontrol.infrastructure.unit_of_work.UnitOfWork` in application code;
    this is the low-level helper it is built on.

    Args:
        factory: The session factory.

    Yields:
        An open session.
    """
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
