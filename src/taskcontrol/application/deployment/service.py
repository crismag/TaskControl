"""Turning published capabilities into the artefacts a scheduler needs.

This is the seam between what an operator declared and what lands on a host. It reads
active capabilities and their published revisions, renders each into a
:class:`~taskcontrol.ports.scheduler_management.DesiredArtefact`, and hands the whole set
to the scheduler adapter.

**The set is always complete.** Never a diff. That is what lets the adapter plan a removal
for something managed on the host but no longer deployed — a capability that was retired,
or one whose lifecycle moved out of active. A diff-based deployment leaves those running
forever, which is the specific failure that makes people stop trusting a deployment tool
and go back to editing crontabs by hand.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator, Sequence
from typing import Any

from taskcontrol.common.errors import NotFoundError
from taskcontrol.domain.common.identifiers import OwnerId
from taskcontrol.domain.common.values import Slug, UtcTimestamp
from taskcontrol.domain.deployment.manifest import InstalledRevision
from taskcontrol.domain.tasks.lifecycle import TaskLifecycleState
from taskcontrol.domain.tasks.revision import TaskRevision
from taskcontrol.domain.tasks.task import Task
from taskcontrol.ports.local_state import InstalledRevisionWriter
from taskcontrol.ports.scheduler_management import (
    ApplyResult,
    DeploymentChange,
    DeploymentPlan,
    DesiredArtefact,
    SchedulerManagement,
    VerificationReport,
)

logger = logging.getLogger(__name__)

_PAGE_SIZE = 200
"""How many capabilities are read at a time when collecting the desired estate."""


class DeploymentService:
    """Deploys published capabilities to a host scheduler.

    Args:
        unit_of_work_factory: Builds a unit of work per read.
        scheduler: The scheduler adapter to deploy through.
        command_builder: Turns a capability into the command line cron will run. Injected
            because how TaskControl is invoked is a property of the installation — the
            path to ``taskctl`` on a real host is rarely just ``taskctl``.
        installed: Where local revision manifests are written. Installed as part of the
            same apply as the artefact, because the artefact and the definition it
            executes must arrive and change together — that is what makes the wrapper's
            "execute installed revision R" a true statement rather than a hope.
    """

    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], Any],
        scheduler: SchedulerManagement,
        command_builder: Callable[[Task], str],
        installed: InstalledRevisionWriter,
    ) -> None:
        """Store the collaborators."""
        self._unit_of_work_factory = unit_of_work_factory
        self._scheduler = scheduler
        self._command_builder = command_builder
        self._installed = installed

    def desired_artefacts(self) -> tuple[DesiredArtefact, ...]:
        """Return every artefact that should exist on this host.

        A capability contributes one artefact when it is active, has a published revision,
        and that revision says how to deploy it. Anything else is skipped with a reason
        logged — silence here would look identical to "correctly deployed".

        Returns:
            The complete desired estate.
        """
        artefacts: list[DesiredArtefact] = []
        active = frozenset({TaskLifecycleState.ACTIVE})

        with self._unit_of_work_factory() as uow:
            # Paged deliberately rather than asking for one enormous page: the estate is
            # the whole point of this method, and a silent truncation at some default
            # limit would read as "everything is deployed" while jobs quietly stopped.
            offset = 0
            while True:
                page = uow.tasks.list_tasks(
                    lifecycle_states=active, limit=_PAGE_SIZE, offset=offset
                )
                if not page:
                    break
                for task in page:
                    artefact = self._artefact_for(task, uow)
                    if artefact is not None:
                        artefacts.append(artefact)
                offset += len(page)

        return tuple(artefacts)

    def _artefact_for(self, task: Task, uow: Any) -> DesiredArtefact | None:
        """Build one capability's artefact, or explain why it has none."""
        if task.active_revision_id is None:
            logger.warning(
                "Skipping a capability with no published revision; it has nothing to run.",
                extra={"slug": task.slug.to_primitive()},
            )
            return None

        revision = uow.revisions.get(task.active_revision_id)
        if revision is None:
            logger.warning(
                "Skipping a capability whose published revision is missing from storage.",
                extra={"slug": task.slug.to_primitive()},
            )
            return None

        return self.artefact_from(task, revision)

    def artefact_from(self, task: Task, revision: TaskRevision) -> DesiredArtefact:
        """Build the artefact for one capability and revision.

        The deployment specification is validated against the slug here rather than at
        write time, because a name cron would silently ignore must be caught while it is
        still a definition rather than a file that looks deployed and never runs.

        Args:
            task: The capability.
            revision: Its published revision.

        Returns:
            The artefact.

        Raises:
            ValidationError: If the slug cannot produce a valid artefact name.
        """
        revision.deployment.assert_deployable_for(task.slug)

        return DesiredArtefact(
            task_id=task.task_id,
            slug=task.slug.to_primitive(),
            deployment=revision.deployment,
            command=self._command_builder(task),
            content_digest=(
                revision.content_digest.to_primitive() if revision.content_digest else "unpublished"
            ),
            schedule=(
                revision.activation_schedule.to_primitive()
                if revision.activation_schedule
                else None
            ),
            description=task.description or task.name,
        )

    def plan(self) -> DeploymentPlan:
        """Compute what deploying the current estate would change.

        Returns:
            The plan, including unchanged entries — "these forty are already correct" is
            part of what makes a plan trustworthy.
        """
        return self._scheduler.plan(self.desired_artefacts())

    def apply(self, plan: DeploymentPlan | None = None) -> ApplyResult:
        """Deploy the current estate, installing each capability's revision alongside it.

        Manifests are installed **before** the artefacts. Cron can fire the moment an
        artefact appears, and a wrapper that woke to find no installed revision would
        refuse to run — so the definition goes down first, and an artefact never points at
        something that is not there yet.

        The reverse is harmless: a manifest with no artefact is inert.

        Args:
            plan: A plan to apply. Computed fresh when omitted — but an operator who has
                reviewed a plan should pass that plan, so what they approved is what runs.

        Returns:
            What was applied, and whether a rollback occurred.
        """
        plan = plan if plan is not None else self.plan()
        self._install_manifests()
        result = self._scheduler.apply(plan)
        if result.succeeded:
            self._uninstall_removed(plan)
        return result

    def _install_manifests(self) -> None:
        """Install a local manifest for every deployable capability."""
        with self._unit_of_work_factory() as uow:
            for task, revision in self._published_pairs(uow):
                self._installed.install(InstalledRevision.install(task, revision))

    def _uninstall_removed(self, plan: DeploymentPlan) -> None:
        """Remove manifests for capabilities whose artefacts were removed.

        Only after a successful apply. Removing a manifest while its artefact is still
        deployed would leave cron firing a wrapper with nothing to execute.
        """
        for entry in plan.entries:
            if entry.change is DeploymentChange.REMOVE:
                self._installed.remove(Slug(entry.slug))

    def _published_pairs(self, uow: Any) -> Iterator[tuple[Task, TaskRevision]]:
        """Yield every active capability with its published revision."""
        active = frozenset({TaskLifecycleState.ACTIVE})
        offset = 0
        while True:
            page = uow.tasks.list_tasks(lifecycle_states=active, limit=_PAGE_SIZE, offset=offset)
            if not page:
                return
            for task in page:
                if task.active_revision_id is None:
                    continue
                revision = uow.revisions.get(task.active_revision_id)
                if revision is not None:
                    yield task, revision
            offset += len(page)

    def verify(self) -> VerificationReport:
        """Read the host and report how it differs from what was published.

        This is how hand-edited crontabs are found. It reads only.

        Returns:
            The report.
        """
        return self._scheduler.verify(self.desired_artefacts())

    def disable(self, slug: Slug, *, actor: OwnerId, at: UtcTimestamp) -> ApplyResult:
        """Suspend a capability and take its artefact off this host.

        Disabling is not undeploying. The definition, its revisions, and its history stay
        exactly where they are; only the thing that causes cron to run it goes away. That
        is what an operator means by "stop this running tonight" — they intend to turn it
        back on.

        The artefact is removed immediately rather than at the next apply. An operator who
        disables a job at 01:50 expects it not to run at 02:00, and "it will stop once
        somebody applies" is not that.

        Args:
            slug: The capability to disable.
            actor: Who is disabling it.
            at: When.

        Returns:
            What was removed from the host.

        Raises:
            NotFoundError: If no capability has that slug.
            DomainRuleViolationError: If its lifecycle state cannot be suspended.
        """
        return self._set_lifecycle(slug, suspend=True, actor=actor, at=at)

    def enable(self, slug: Slug, *, actor: OwnerId, at: UtcTimestamp) -> ApplyResult:
        """Return a suspended capability to service and redeploy its artefact.

        Args:
            slug: The capability to enable.
            actor: Who is enabling it.
            at: When.

        Returns:
            What was written to the host.

        Raises:
            NotFoundError: If no capability has that slug.
            DomainRuleViolationError: If its lifecycle state cannot be resumed.
        """
        return self._set_lifecycle(slug, suspend=False, actor=actor, at=at)

    def _set_lifecycle(
        self, slug: Slug, *, suspend: bool, actor: OwnerId, at: UtcTimestamp
    ) -> ApplyResult:
        """Change a capability's lifecycle state, then bring the host back into line.

        The state change commits before the host is touched. If the deployment then fails,
        the recorded intent is still correct and the next apply completes it — whereas
        deploying first and failing to record would leave the host and the control plane
        disagreeing with nothing to reconcile them.
        """
        with self._unit_of_work_factory() as uow:
            task = uow.tasks.get_by_slug(slug)
            if task is None:
                raise NotFoundError(
                    f"No capability named '{slug}'.", details={"slug": slug.to_primitive()}
                )
            version = uow.tasks.version_of(task.task_id)
            changed = (
                task.suspend(updated_by=actor, updated_at=at)
                if suspend
                else task.resume(updated_by=actor, updated_at=at)
            )
            uow.tasks.update(changed, expected_version=version or 0)
            uow.commit()

        return self.apply()

    def remove(self, artefacts: Sequence[DesiredArtefact]) -> ApplyResult:
        """Undeploy specific capabilities.

        Args:
            artefacts: What to remove.

        Returns:
            What was removed.
        """
        return self._scheduler.remove([artefact.task_id for artefact in artefacts])
