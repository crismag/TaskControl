"""Database fixtures for persistence tests.

Every persistence test runs against each available backend. SQLite always runs; PostgreSQL
runs when ``TASKCONTROL_TEST_POSTGRES_URL`` is set and is skipped with a clear message
otherwise — a silent skip would let a PostgreSQL regression reach a release unnoticed.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, text

from taskcontrol.adapters.persistence.models import Base
from taskcontrol.adapters.persistence.unit_of_work import UnitOfWork
from taskcontrol.infrastructure.database import create_database_engine, create_session_factory
from taskcontrol.infrastructure.migrations import upgrade_to_head

POSTGRES_URL_VARIABLE = "TC_TEST_POSTGRES_URL"
"""Deliberately **not** prefixed ``TASKCONTROL_``.

That prefix belongs to application settings, and the application rejects unknown variables
carrying it — correctly, since a mistyped setting must fail loudly. A harness variable using
the same prefix is therefore either stripped by environment isolation or rejected as a typo.
Test configuration gets its own namespace."""


def postgres_url() -> str | None:
    """Return the PostgreSQL URL to test against, when one is configured."""
    return os.environ.get(POSTGRES_URL_VARIABLE) or None


@pytest.fixture(params=["sqlite", "postgresql"])
def backend(request: pytest.FixtureRequest) -> str:
    """Parameterise a test over every supported backend."""
    if request.param == "postgresql" and not postgres_url():
        pytest.skip(
            f"PostgreSQL tests need {POSTGRES_URL_VARIABLE}, for example "
            f"{POSTGRES_URL_VARIABLE}="
            "postgresql+psycopg://taskcontrol@localhost/taskcontrol_test"
        )
    return str(request.param)


@pytest.fixture
def engine(backend: str, tmp_path: Path) -> Iterator[Engine]:
    """Return a migrated engine for the current backend.

    The schema is created by running the real migrations rather than
    ``Base.metadata.create_all``. That way the tests exercise what an installation actually
    gets, and a migration that disagrees with the models fails here.
    """
    if backend == "sqlite":
        url = f"sqlite+pysqlite:///{(tmp_path / 'test.db').as_posix()}"
    else:
        url = postgres_url() or ""

    engine = create_database_engine(url)
    if backend == "postgresql":
        _drop_everything(engine)

    upgrade_to_head(engine)
    try:
        yield engine
    finally:
        if backend == "postgresql":
            _drop_everything(engine)
        engine.dispose()


def _drop_everything(engine: Engine) -> None:
    """Reset a PostgreSQL database between tests.

    The table list is derived from the model metadata rather than hard-coded, so a table
    added in a later wave cannot be forgotten here. An earlier hard-coded version missed
    the Wave 3 execution tables, which left stale rows between PostgreSQL runs — a failure
    that never appears on SQLite, because each SQLite test gets a fresh file.

    Dropped in reverse dependency order, with CASCADE, so foreign keys do not block it.
    """
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(text(f'DROP TABLE IF EXISTS "{table.name}" CASCADE'))
        connection.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))


@pytest.fixture
def unit_of_work(engine: Engine) -> UnitOfWork:
    """Return a unit of work bound to the current backend."""
    return UnitOfWork(create_session_factory(engine))
