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
from collections.abc import Callable, Sequence
from typing import Any

from taskcontrol.domain.tasks.lifecycle import TaskLifecycleState
from taskcontrol.domain.tasks.revision import TaskRevision
from taskcontrol.domain.tasks.task import Task
from taskcontrol.ports.scheduler_management import (
    ApplyResult,
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
    """

    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], Any],
        scheduler: SchedulerManagement,
        command_builder: Callable[[Task], str],
    ) -> None:
        """Store the collaborators."""
        self._unit_of_work_factory = unit_of_work_factory
        self._scheduler = scheduler
        self._command_builder = command_builder

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
        """Deploy the current estate.

        Args:
            plan: A plan to apply. Computed fresh when omitted — but an operator who has
                reviewed a plan should pass that plan, so what they approved is what runs.

        Returns:
            What was applied, and whether a rollback occurred.
        """
        return self._scheduler.apply(plan if plan is not None else self.plan())

    def verify(self) -> VerificationReport:
        """Read the host and report how it differs from what was published.

        This is how hand-edited crontabs are found. It reads only.

        Returns:
            The report.
        """
        return self._scheduler.verify(self.desired_artefacts())

    def remove(self, artefacts: Sequence[DesiredArtefact]) -> ApplyResult:
        """Undeploy specific capabilities.

        Args:
            artefacts: What to remove.

        Returns:
            What was removed.
        """
        return self._scheduler.remove([artefact.task_id for artefact in artefacts])
