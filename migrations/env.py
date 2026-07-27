"""Alembic environment.

The database URL comes from TaskControl settings rather than from ``alembic.ini``, so a
migration can never be applied to a different database from the one the application uses.

``render_as_batch`` is enabled for SQLite: it cannot ``ALTER`` most things in place, and
without batch mode a future column change would fail on the backend most installations run.
"""

from __future__ import annotations

from alembic import context
from sqlalchemy import Connection

from taskcontrol.adapters.persistence.models import Base
from taskcontrol.infrastructure.database import create_database_engine, database_url, is_sqlite
from taskcontrol.infrastructure.settings import load_settings

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    """Return the URL to migrate, preferring one supplied by the caller."""
    return config.get_main_option("sqlalchemy.url") or database_url(load_settings())


def run_migrations_offline() -> None:
    """Emit SQL without connecting, for review or manual application."""
    url = _url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=is_sqlite(url),
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run(connection: Connection, *, sqlite: bool) -> None:
    """Run migrations against an open connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=sqlite,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations against the configured database."""
    connectable = config.attributes.get("connection", None)
    if connectable is not None:
        _run(connectable, sqlite=connectable.dialect.name == "sqlite")
        return

    url = _url()
    engine = create_database_engine(url)
    try:
        with engine.connect() as connection:
            _run(connection, sqlite=is_sqlite(url))
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
