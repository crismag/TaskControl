"""Bringing journalled activations back into the control plane.

A run that happened while the database was down is not lost, but it is not yet *known*.
Reconciliation is what closes that gap, and it has one property that matters above the
rest: **it is idempotent**.

That comes from the execution identity being allocated by the wrapper *before* the work
ran, and journalled with it. Ingestion keys on that identity, so replaying a journal ten
times produces one execution record. The alternative — matching on task and timestamp —
turns a clock adjustment or a retry into a duplicate history.

The journal is cleared only once every entry it holds is durably recorded. A crash
part-way leaves entries to be ingested again, which is harmless precisely because
ingestion is idempotent.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from taskcontrol.domain.execution.execution import Execution
from taskcontrol.domain.execution.journal import JournalEntry
from taskcontrol.domain.execution.vocabulary import ExecutionState
from taskcontrol.ports.local_state import ActivationJournalPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    """What reconciling the local journal did.

    Attributes:
        ingested: Entries recorded in the control plane for the first time.
        already_known: Entries whose execution was already recorded — the ordinary result
            of reconciling twice, and not a problem.
        unreadable: Journal lines that could not be parsed, usually a torn write. Reported
            rather than hidden: nothing can be done about them, but an operator counting
            runs needs to know something was lost.
        cleared: Whether the journal was cleared afterwards.
    """

    ingested: int = 0
    already_known: int = 0
    unreadable: int = 0
    cleared: bool = False

    @property
    def total_seen(self) -> int:
        """How many entries were read."""
        return self.ingested + self.already_known


class ReconciliationService:
    """Ingests journalled activations into the control plane.

    Args:
        unit_of_work_factory: Builds a unit of work per ingest.
        journal: The local journal to reconcile.
    """

    def __init__(
        self, *, unit_of_work_factory: Callable[[], Any], journal: ActivationJournalPort
    ) -> None:
        """Store the collaborators."""
        self._unit_of_work_factory = unit_of_work_factory
        self._journal = journal

    def reconcile(self) -> ReconciliationReport:
        """Record every journalled activation that is not already known.

        Returns:
            What was ingested, and whether the journal was cleared.

        Raises:
            TransientInfrastructureError: If the control plane is still unreachable. The
                journal is left untouched, so reconciling again later loses nothing.
        """
        entries = list(self._journal.entries())
        unreadable = self._journal.unreadable_line_count()

        if not entries:
            if unreadable:
                logger.warning(
                    "The local journal holds %d unreadable line(s) and nothing to ingest.",
                    unreadable,
                )
            return ReconciliationReport(unreadable=unreadable)

        ingested = 0
        already_known = 0

        with self._unit_of_work_factory() as uow:
            for entry in entries:
                if uow.executions.get(entry.execution_id) is not None:
                    already_known += 1
                    continue
                uow.executions.add(_execution_from(entry))
                ingested += 1
            uow.commit()

        # Cleared only after the commit. A crash before this point leaves entries to be
        # ingested again, which is harmless because ingestion keys on execution identity.
        self._journal.truncate()

        logger.info(
            "Reconciled the local activation journal.",
            extra={
                "ingested": ingested,
                "already_known": already_known,
                "unreadable": unreadable,
            },
        )
        return ReconciliationReport(
            ingested=ingested,
            already_known=already_known,
            unreadable=unreadable,
            cleared=True,
        )


def _execution_from(entry: JournalEntry) -> Execution:
    """Build a terminal execution record from a journal entry.

    The record is created already finished. This run is history: it happened, it ended, and
    nothing about it is still in progress. Creating it pending and transitioning would
    invent states it never passed through while the control plane was watching.

    Attempts are deliberately empty. ADR 0027 keeps captured output out of the journal, so
    there is no attempt detail to reconstruct — and inventing an attempt record with no
    evidence behind it would be worse than recording none.
    """
    return Execution(
        execution_id=entry.execution_id,
        task_id=entry.task_id,
        revision_id=entry.revision_id,
        trigger_source=entry.trigger_source,
        requested_at=entry.started_at,
        state=ExecutionState.FINISHED,
        outcome=entry.outcome,
        reason_code=entry.reason_code,
        explanation=_explanation_for(entry),
        started_at=entry.started_at,
        finished_at=entry.finished_at,
    )


def _explanation_for(entry: JournalEntry) -> str:
    """Return an explanation that says where this record came from.

    An operator reading execution history months later must be able to tell a reconciled
    run from one TaskControl watched: it has no attempt detail and no captured output, and
    the reason for that should be in the record rather than in somebody's memory.
    """
    detail = entry.explanation or f"Outcome {entry.outcome}."
    return (
        f"{detail} Reconciled from a local journal: this ran while TaskControl's control "
        "state was unreachable, so no attempt detail was captured."
    )
