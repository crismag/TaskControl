"""Assembling the runtime for a CLI invocation.

The CLI is a transport: it parses arguments and prints results. Building the object graph
is composition, so it lives here rather than inside a command body — and the same
assembly will serve the API and the scheduler in later waves.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable

from taskcontrol.adapters.clock import SystemClock
from taskcontrol.adapters.executors import default_registry
from taskcontrol.adapters.locking.durable import DurableOverlapLock
from taskcontrol.adapters.persistence.claim_store import SqlAlchemyClaimStore
from taskcontrol.adapters.persistence.unit_of_work import UnitOfWork
from taskcontrol.application.runtime import RuntimeService
from taskcontrol.common.errors import NotFoundError, ValidationError
from taskcontrol.domain.common.identifiers import TaskId
from taskcontrol.domain.common.values import Slug
from taskcontrol.infrastructure.database import (
    create_database_engine,
    create_session_factory,
    database_url,
)
from taskcontrol.infrastructure.settings import Settings


def build_runtime(settings: Settings) -> tuple[RuntimeService, Callable[[str], TaskId]]:
    """Build a runtime and a task resolver.

    Overlap protection is durable (ADR 0023), which is what makes `OverlapPolicy.FORBID`
    mean something under cron-backed activation. R1 measured the alternative: with a
    process-local lock, two concurrent activations of one task both ran.

    Args:
        settings: Validated settings.

    Returns:
        The runtime, and a function turning a user-supplied identifier or slug into a
        ``TaskId``.
    """
    engine = create_database_engine(database_url(settings))
    session_factory = create_session_factory(engine)

    def unit_of_work_factory() -> UnitOfWork:
        return UnitOfWork(session_factory)

    clock = SystemClock()
    runtime = RuntimeService(
        unit_of_work_factory=unit_of_work_factory,
        executors=default_registry(),
        lock=DurableOverlapLock(SqlAlchemyClaimStore(session_factory, clock)),
        clock=clock,
    )

    def resolve(reference: str) -> TaskId:
        """Turn an identifier or slug into a task identifier.

        Accepting both is a usability choice: an operator reaching for the CLI in an
        incident knows the slug, not a UUID.

        Args:
            reference: A task identifier or slug.

        Returns:
            The task identifier.

        Raises:
            NotFoundError: If no task matches.
        """
        # A well-formed identifier is used directly; anything else is tried as a slug,
        # which is what an operator reaching for the CLI in an incident actually knows.
        with contextlib.suppress(ValidationError):
            return TaskId(reference)

        with unit_of_work_factory() as uow:
            task = uow.tasks.get_by_slug(Slug(reference))
        if task is None:
            raise NotFoundError(
                "No task with that identifier or slug.", details={"reference": reference}
            )
        return task.task_id

    return runtime, resolve
