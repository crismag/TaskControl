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
from taskcontrol.adapters.local import ActivationJournal, InstalledRevisionStore
from taskcontrol.adapters.locking.durable import DurableOverlapLock
from taskcontrol.adapters.persistence.claim_store import SqlAlchemyClaimStore
from taskcontrol.adapters.persistence.unit_of_work import UnitOfWork
from taskcontrol.adapters.schedulers.cron import (
    CronLayout,
    CronSchedulerManagement,
    FileCrontab,
    FilesystemDirectory,
    UserCrontab,
)
from taskcontrol.application.activation import ActivationService, ReconciliationService
from taskcontrol.application.deployment import DeploymentService
from taskcontrol.application.runtime import RuntimeService
from taskcontrol.common.errors import NotFoundError, ValidationError
from taskcontrol.domain.common.identifiers import TaskId
from taskcontrol.domain.common.values import Slug
from taskcontrol.domain.deployment.strategies import PeriodicClassification
from taskcontrol.domain.tasks.task import Task
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


def build_deployment_service(settings: Settings) -> DeploymentService:
    """Build a deployment service over this host's cron layout.

    Every path comes from settings, because distributions disagree about them and a wrong
    path must be something an operator can correct rather than a constant they patch.

    Only the classifications whose run-parts directory actually exists are configured. A
    host without ``/etc/cron.weekly`` should be told that plainly when something tries to
    deploy there, rather than have TaskControl create a directory cron has never been told
    to read.

    Args:
        settings: Validated settings.

    Returns:
        The deployment service.
    """
    engine = create_database_engine(database_url(settings))
    session_factory = create_session_factory(engine)

    run_parts = {
        classification: FilesystemDirectory(
            settings.run_parts_root / classification.run_parts_directory_name
        )
        for classification in PeriodicClassification
        if (settings.run_parts_root / classification.run_parts_directory_name).is_dir()
    }

    layout = CronLayout(
        user_crontab=UserCrontab(user=settings.cron_user or None, command=settings.cron_command),
        system_crontab=FileCrontab(settings.cron_system_crontab),
        cron_d=FilesystemDirectory(settings.cron_d_dir),
        run_parts=run_parts,
    )

    def command_for(task: Task) -> str:
        """Return the command line cron will run for a capability.

        ``activate`` rather than ``run``: a cron-woken process must be able to decide what
        to do from locally installed state, and ``run`` reaches the database before it can
        do anything at all (R1 Finding 2). The two commands differ in exactly that.

        The slug rather than the identifier, because an operator reading their own crontab
        should recognise the job, and the slug is what they named it.
        """
        return f"{settings.taskctl_command} activate {task.slug.to_primitive()}"

    return DeploymentService(
        unit_of_work_factory=lambda: UnitOfWork(session_factory),
        scheduler=CronSchedulerManagement(layout),
        command_builder=command_for,
        installed=installed_revision_store(settings),
    )


def installed_revision_store(settings: Settings) -> InstalledRevisionStore:
    """Return the store holding this host's installed revisions.

    Args:
        settings: Validated settings.

    Returns:
        The store.
    """
    return InstalledRevisionStore(settings.data_dir / "installed")


def activation_journal(settings: Settings) -> ActivationJournal:
    """Return this host's local activation journal.

    Args:
        settings: Validated settings.

    Returns:
        The journal.
    """
    return ActivationJournal(settings.data_dir / "journal")


def build_activation_service(settings: Settings) -> ActivationService:
    """Build the service a cron-woken wrapper runs.

    The runtime is built **lazily**, inside a factory. That is deliberate: building it
    opens the database, and failing to open the database is precisely the signal that the
    control plane is unreachable. Building it eagerly here would move that failure out of
    the activation policy's reach and back into a traceback.

    Args:
        settings: Validated settings.

    Returns:
        The activation service.
    """

    def runtime() -> RuntimeService:
        return build_runtime(settings)[0]

    return ActivationService(
        manifests=installed_revision_store(settings),
        journal=activation_journal(settings),
        executors=default_registry(),
        clock=SystemClock(),
        runtime_factory=runtime,
    )


def build_reconciliation_service(settings: Settings) -> ReconciliationService:
    """Build the service that ingests journalled activations.

    Args:
        settings: Validated settings.

    Returns:
        The reconciliation service.
    """
    session_factory = create_session_factory(create_database_engine(database_url(settings)))
    return ReconciliationService(
        unit_of_work_factory=lambda: UnitOfWork(session_factory),
        journal=activation_journal(settings),
    )
