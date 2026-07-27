"""The transaction boundary.

An application use case decides what constitutes one consistent change; this is the object
it says so with. Everything inside a `with` block commits together or not at all.

The unit of work owns the session. Repositories borrow it and never outlive the block, so
a stale ORM instance cannot leak into a caller that has already committed.

This lives in the persistence adapter rather than in ``infrastructure/``, where the
blueprint originally placed it. It constructs SQLAlchemy repositories and owns a
SQLAlchemy session, which makes it a persistence concern rather than a neutral
process-level one — the architecture test made that obvious the moment the import existed.
"""

from __future__ import annotations

from types import TracebackType
from typing import Literal, Self

from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from taskcontrol.adapters.persistence.repositories import (
    SqlAlchemyExecutionRepository,
    SqlAlchemyTaskRepository,
    SqlAlchemyTaskRevisionRepository,
)
from taskcontrol.common.errors import (
    ConflictError,
    TaskControlError,
    TransientInfrastructureError,
)
from taskcontrol.ports.repositories import ConcurrencyConflictError


class UnitOfWork:
    """One database transaction, with the repositories that participate in it.

    Rolls back on any exception, including one raised by the caller's own code after a
    successful write. Nothing commits unless the block completes.

    Args:
        session_factory: Builds the session this unit of work owns.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self._committed = False

    def __enter__(self) -> Self:
        """Open the transaction and build the repositories."""
        self._session = self._session_factory()
        self._committed = False
        self.tasks = SqlAlchemyTaskRepository(self._session)
        self.revisions = SqlAlchemyTaskRevisionRepository(self._session)
        self.executions = SqlAlchemyExecutionRepository(self._session)
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        """Close the transaction, rolling back unless the block committed.

        Returns:
            Always ``False`` — an exception is never suppressed. A caller must not be able
            to believe a failed write succeeded.
        """
        session = self._require_session()
        try:
            if exception_type is not None or not self._committed:
                session.rollback()
        except SQLAlchemyError:
            # The rollback itself failed, which means the connection is already gone. The
            # transaction is not committed, which is what matters; the original exception
            # is the one worth reporting.
            pass
        finally:
            session.close()
            self._session = None

        # A vendor exception escaping here is what produced the forty-three lines of
        # SQLAlchemy traceback an operator saw in R1 Finding 3. Translated at the boundary
        # it crosses, which is this one.
        if isinstance(exception, SQLAlchemyError):
            raise _translate(exception) from exception
        return False

    def commit(self) -> None:
        """Commit the transaction.

        Raises:
            ConflictError: If a concurrent write beat this one. Translated here so callers
                see the taxonomy rather than a port-level or vendor exception.
        """
        session = self._require_session()
        try:
            session.commit()
        except ConcurrencyConflictError as exc:
            session.rollback()
            raise ConflictError(str(exc)) from exc
        except SQLAlchemyError as exc:
            session.rollback()
            raise _translate(exc) from exc
        self._committed = True

    def rollback(self) -> None:
        """Discard everything written in this transaction."""
        self._require_session().rollback()
        self._committed = False

    @property
    def session(self) -> Session:
        """The underlying session.

        Exposed for migrations and tests only. Application code uses the repositories;
        reaching for the session here is a sign that a repository is missing a method.
        """
        return self._require_session()

    def _require_session(self) -> Session:
        """Return the open session, or explain that the block was never entered."""
        if self._session is None:
            message = "The unit of work is not active. Use it as a context manager."
            raise RuntimeError(message)
        return self._session


def _translate(error: SQLAlchemyError) -> TaskControlError:
    """Turn a vendor exception into the product's own taxonomy.

    Deliberately lossy. The operator gets a sentence naming what could not be done; the
    driver's message, the connection string, and the library's stack stay in the chained
    cause, where a log at debug level can still reach them.

    Args:
        error: The vendor exception.

    Returns:
        The error to raise instead.
    """
    if isinstance(error, DBAPIError) and error.connection_invalidated:
        return TransientInfrastructureError(
            "Lost the connection to TaskControl's database part-way through. Nothing was "
            "committed. Retrying is safe."
        )
    return TransientInfrastructureError(
        "Could not reach TaskControl's database, so this operation was not recorded. "
        "Check that the database is running and that the configured connection is correct."
    )
