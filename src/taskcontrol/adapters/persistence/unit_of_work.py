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

from sqlalchemy.orm import Session, sessionmaker

from taskcontrol.adapters.persistence.repositories import (
    SqlAlchemyTaskRepository,
    SqlAlchemyTaskRevisionRepository,
)
from taskcontrol.common.errors import ConflictError
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
        finally:
            session.close()
            self._session = None
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
