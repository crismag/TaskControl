"""The journal entry — a dispatch record, not a log.

ADR 0027 settled the shape by settling a prior question: TaskControl logs **dispatch**, and
the runnable logs its own work. So this is small and fixed — identity, revision, timing, how
the process ended, and the classified outcome. **No captured output.**

That is precisely what makes it writable when things are already degraded. A record that
had to carry arbitrary application output would be least likely to succeed exactly when it
matters most.

The execution identity is allocated by the wrapper *before* the work runs, and carried here.
Reconciliation keys on it, which makes ingestion idempotent by primary key: replaying a
journal ten times produces one execution record. Matching on task and timestamp instead
would turn a clock adjustment into a duplicate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self

from taskcontrol.common.errors import ValidationError
from taskcontrol.domain.common.identifiers import ExecutionId, TaskId, TaskRevisionId
from taskcontrol.domain.common.values import ContentDigest, Slug, UtcTimestamp
from taskcontrol.domain.execution.execution import TriggerSource
from taskcontrol.domain.execution.results import TerminationCause
from taskcontrol.domain.execution.vocabulary import ExecutionOutcome, ReasonCode

JOURNAL_FORMAT_VERSION = 1
"""Version of the entry envelope. A reader that does not understand it must refuse."""


@dataclass(frozen=True, slots=True)
class JournalEntry:
    """One activation, recorded locally because the control plane could not be reached.

    Fixed shape by design. Every field here is dispatch metadata; nothing grows with what
    the task printed, how long its output was, or what it did.

    Attributes:
        execution_id: Allocated before the work ran. Reconciliation keys on this, which is
            what makes replaying the journal idempotent.
        task_id: The capability.
        slug: Its stable name, for a human reading the file.
        revision_id: Exactly which revision ran.
        content_digest: The digest of that revision, so a reconciled record can be checked
            against what was published.
        trigger_source: What activated it.
        started_at: When the process started.
        finished_at: When it ended.
        outcome: The classified outcome.
        reason_code: Why, where the outcome carries one.
        exit_code: The process exit status, when it exited.
        signal_number: The signal that ended it, when one did.
        termination_cause: Why TaskControl terminated it, recorded at request time and
            never inferred from the signal (ADR 0020).
        explanation: One sentence an operator can act on.
    """

    execution_id: ExecutionId
    task_id: TaskId
    slug: Slug
    revision_id: TaskRevisionId
    content_digest: ContentDigest
    trigger_source: TriggerSource
    started_at: UtcTimestamp
    finished_at: UtcTimestamp
    outcome: ExecutionOutcome
    reason_code: ReasonCode | None = None
    exit_code: int | None = None
    signal_number: int | None = None
    termination_cause: TerminationCause = TerminationCause.NOT_TERMINATED
    explanation: str = ""

    def to_primitive(self) -> dict[str, Any]:
        """Return the entry as plain data.

        Returns:
            A mapping. Contains no captured output, by design and by ADR 0027.
        """
        return {
            "format_version": JOURNAL_FORMAT_VERSION,
            "execution_id": self.execution_id.to_primitive(),
            "task_id": self.task_id.to_primitive(),
            "slug": self.slug.to_primitive(),
            "revision_id": self.revision_id.to_primitive(),
            "content_digest": self.content_digest.to_primitive(),
            "trigger_source": str(self.trigger_source),
            "started_at": self.started_at.to_primitive(),
            "finished_at": self.finished_at.to_primitive(),
            "outcome": str(self.outcome),
            "reason_code": str(self.reason_code) if self.reason_code else None,
            "exit_code": self.exit_code,
            "signal_number": self.signal_number,
            "termination_cause": str(self.termination_cause),
            "explanation": self.explanation,
        }

    @classmethod
    def from_primitive(cls, data: dict[str, Any]) -> Self:
        """Rebuild an entry from a journal line.

        Args:
            data: The parsed line.

        Returns:
            The entry.

        Raises:
            ValidationError: If the line is malformed or written by a newer TaskControl.
        """
        version = data.get("format_version")
        if version != JOURNAL_FORMAT_VERSION:
            raise ValidationError(
                f"This journal entry is format version {version!r}, and this build "
                f"understands {JOURNAL_FORMAT_VERSION}.",
                details={"found": version, "supported": JOURNAL_FORMAT_VERSION},
            )

        try:
            reason = data.get("reason_code")
            return cls(
                execution_id=ExecutionId(data["execution_id"]),
                task_id=TaskId(data["task_id"]),
                slug=Slug(data["slug"]),
                revision_id=TaskRevisionId(data["revision_id"]),
                content_digest=ContentDigest(data["content_digest"]),
                trigger_source=TriggerSource(data["trigger_source"]),
                started_at=UtcTimestamp.from_primitive(data["started_at"]),
                finished_at=UtcTimestamp.from_primitive(data["finished_at"]),
                outcome=ExecutionOutcome(data["outcome"]),
                reason_code=ReasonCode(reason) if reason else None,
                exit_code=data.get("exit_code"),
                signal_number=data.get("signal_number"),
                termination_cause=TerminationCause(
                    data.get("termination_cause", TerminationCause.NOT_TERMINATED)
                ),
                explanation=data.get("explanation", ""),
            )
        except KeyError as error:
            raise ValidationError(
                "A journal entry is missing a required field.",
                details={"missing_field": str(error.args[0])},
            ) from error
