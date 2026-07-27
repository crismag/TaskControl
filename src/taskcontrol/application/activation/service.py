r"""What happens when cron wakes a wrapper.

This is the seam ADR 0024 needed and R1 Finding 2 said did not exist. The wrapper does not
ask *"what is the current definition of this task?"* — it loads an installed revision from
the local manifest and asks the control plane only to **record**, never to **decide**.

```text
cron fires
    |
load installed revision locally      <- always; never needs the control plane
    |
try to reach the control plane
    |                    \\
reachable                 unreachable
    |                          |
normal recorded run       activation policy decides
                               |                    \\
                  require_control_state    continue_with_local_journal
                               |                    |
                        refuse, exit 75      run, journal, exit on the outcome
```

Exit code 75 (``EX_TEMPFAIL``) for a strict refusal, not 1. Cron reports both as failure,
but a script or monitor reading the code can tell "TaskControl declined to run because it
could not record" from "the work ran and failed" — and those need different responses.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from taskcontrol.application.runtime import RunRequest, RuntimeService
from taskcontrol.common.errors import (
    PermanentInfrastructureError,
    TransientInfrastructureError,
)
from taskcontrol.domain.common.identifiers import ExecutionId
from taskcontrol.domain.common.values import Slug
from taskcontrol.domain.deployment.manifest import InstalledRevision
from taskcontrol.domain.execution.execution import TriggerSource
from taskcontrol.domain.execution.journal import JournalEntry
from taskcontrol.domain.execution.vocabulary import ExecutionOutcome
from taskcontrol.domain.policies.classification import classify_process_result
from taskcontrol.ports.clock import Clock
from taskcontrol.ports.executor import ExecutionRequest, Executor
from taskcontrol.ports.local_state import ActivationJournalPort, InstalledRevisionReader

logger = logging.getLogger(__name__)

EXIT_SUCCESS = 0
EXIT_FAILED = 1
EXIT_DECLINED = 75
"""``EX_TEMPFAIL``. TaskControl declined to run because it could not record the run.

Distinct from 1 on purpose: "the work ran and failed" and "the work deliberately did not
run" call for different responses, and cron reports both as failure either way.
"""
EXIT_UNRECORDED = 70
"""``EX_SOFTWARE``. The work ran and TaskControl could not record that it ran.

The loudest thing available, because it is the one state nobody can reconstruct: side
effects exist and nothing says so (ADR 0027).
"""


@dataclass(frozen=True, slots=True)
class ActivationResult:
    """What an activation did, in terms a shell can act on.

    Attributes:
        exit_code: What the wrapper should exit with.
        outcome: The classified outcome, where the work ran.
        degraded: Whether this ran without the control plane.
        journalled: Whether it was recorded locally instead of centrally.
        explanation: One sentence for the operator.
    """

    exit_code: int
    outcome: ExecutionOutcome | None = None
    degraded: bool = False
    journalled: bool = False
    explanation: str = ""


class ActivationService:
    """Runs one capability from a locally installed revision.

    Args:
        manifests: Where installed revisions are read from.
        journal: Where degraded activations are recorded.
        executors: Chooses the adapter for an action.
        clock: Supplies time.
        runtime_factory: Builds the recorded runtime. Called lazily and allowed to fail —
            failing to build it *is* the signal that the control plane is unreachable.
    """

    def __init__(
        self,
        *,
        manifests: InstalledRevisionReader,
        journal: ActivationJournalPort,
        executors: Any,
        clock: Clock,
        runtime_factory: Callable[[], RuntimeService],
    ) -> None:
        """Store the collaborators."""
        self._manifests = manifests
        self._journal = journal
        self._executors = executors
        self._clock = clock
        self._runtime_factory = runtime_factory

    def activate(self, slug: Slug, *, trigger_source: TriggerSource) -> ActivationResult:
        """Activate one capability.

        The manifest is loaded and verified first, before anything is attempted against the
        control plane. A capability whose local definition is missing or has been tampered
        with does not run, whether or not the database is up.

        Args:
            slug: Which capability.
            trigger_source: What activated it.

        Returns:
            What happened, and what the wrapper should exit with.

        Raises:
            NotFoundError: If nothing is installed for this capability.
            ValidationError: If the installed manifest is malformed or has been modified.
        """
        installed = self._manifests.load(slug)

        try:
            runtime = self._runtime_factory()
            result = runtime.run(
                RunRequest(task_id=installed.task_id, trigger_source=trigger_source)
            )
        except (TransientInfrastructureError, PermanentInfrastructureError) as error:
            logger.warning(
                "Control plane unreachable at activation; applying the activation policy.",
                extra={
                    "slug": slug.to_primitive(),
                    "activation_policy": str(installed.activation_policy),
                    "reason": error.message,
                },
            )
            return self._activate_degraded(installed, trigger_source=trigger_source)

        return ActivationResult(
            exit_code=EXIT_SUCCESS if result.succeeded else EXIT_FAILED,
            outcome=result.execution.outcome,
            explanation=result.execution.explanation,
        )

    def _activate_degraded(
        self, installed: InstalledRevision, *, trigger_source: TriggerSource
    ) -> ActivationResult:
        """Decide and act with the control plane unreachable.

        The decision is read from the manifest, never from the database — a wrapper that
        had to ask the control plane for its own degraded-mode policy would have no policy
        exactly when it needed one.
        """
        if not installed.activation_policy.executes_without_control_state:
            explanation = (
                f"'{installed.slug}' requires a durable record of every run, and "
                "TaskControl's control state is unreachable. The work was not started. "
                "It will be reconciled as an infrastructure failure once the database "
                "returns."
            )
            logger.error(explanation, extra={"slug": installed.slug.to_primitive()})
            return ActivationResult(exit_code=EXIT_DECLINED, degraded=True, explanation=explanation)

        if installed.requires_unresolvable_secrets:
            # Manifests carry references, never values. Running with a silently incomplete
            # environment would be worse than not running: the work would appear to have
            # happened.
            explanation = (
                f"'{installed.slug}' needs secrets that only the control plane can "
                "resolve, and it is unreachable. Running with an incomplete environment "
                "would look like success, so the work was not started."
            )
            logger.error(explanation, extra={"slug": installed.slug.to_primitive()})
            return ActivationResult(exit_code=EXIT_DECLINED, degraded=True, explanation=explanation)

        return self._run_and_journal(installed, trigger_source=trigger_source)

    def _run_and_journal(
        self, installed: InstalledRevision, *, trigger_source: TriggerSource
    ) -> ActivationResult:
        """Run the work locally and record it in the journal.

        No overlap claim is taken, and none can be: the claim store is the database that is
        unreachable. This is stated in the explanation rather than hidden, because it is a
        real reduction in guarantee that an operator reconciling later must know about.

        Nothing is journalled before the work runs. A pre-write gate would mean a full disk
        stops the backups, which is the failure this mode exists to survive.
        """
        execution_id = ExecutionId.generate()
        started_at = self._clock.now()

        executor: Executor = self._executors.get(installed.action.executor_type)
        report = executor.run(
            ExecutionRequest(
                action=installed.action,
                environment=self._local_environment(installed),
                timeout=installed.controls.timeout.run_timeout,
                termination_grace=installed.controls.timeout.termination_grace,
            )
        )
        finished_at = self._clock.now()
        classification = classify_process_result(report.result)

        entry = JournalEntry(
            execution_id=execution_id,
            task_id=installed.task_id,
            slug=installed.slug,
            revision_id=installed.revision_id,
            content_digest=installed.content_digest,
            trigger_source=trigger_source,
            started_at=started_at,
            finished_at=finished_at,
            outcome=classification.outcome,
            reason_code=classification.reason_code,
            exit_code=report.result.exit_code,
            signal_number=report.result.signal_number,
            termination_cause=report.result.termination_cause,
            explanation=(
                f"{classification.explanation} Run without the control plane, so no "
                "overlap protection was in force."
            ),
        )

        try:
            self._journal.append(entry)
        except TransientInfrastructureError as error:
            # The work has already run. Its side effects exist and cannot be withdrawn, and
            # now nothing records that they happened. This is the loudest case there is
            # (ADR 0027): say so and exit distinctly, so cron's own reporting escalates it.
            logger.critical(
                "Ran '%s' (revision %s, outcome %s) and could not write the local "
                "journal. This run is unrecorded and reconciliation will not find it.",
                installed.slug,
                installed.revision_id,
                classification.outcome,
                extra={
                    "slug": installed.slug.to_primitive(),
                    "revision_id": installed.revision_id.to_primitive(),
                    "outcome": str(classification.outcome),
                    "reason": error.message,
                },
            )
            return ActivationResult(
                exit_code=EXIT_UNRECORDED,
                outcome=classification.outcome,
                degraded=True,
                explanation=(
                    f"'{installed.slug}' ran, and TaskControl could not record that it "
                    "ran. Treat this run as having happened; there is no record of it."
                ),
            )

        return ActivationResult(
            exit_code=EXIT_SUCCESS
            if classification.outcome is ExecutionOutcome.SUCCEEDED
            else EXIT_FAILED,
            outcome=classification.outcome,
            degraded=True,
            journalled=True,
            explanation=entry.explanation,
        )

    def _local_environment(self, installed: InstalledRevision) -> dict[str, str]:
        """Resolve the environment from the manifest alone.

        Only literal bindings. Secret references were refused before reaching here, so this
        never has to decide what to do about one.
        """
        return {
            binding.name: binding.value
            for binding in installed.action.environment
            if binding.value is not None
        }
