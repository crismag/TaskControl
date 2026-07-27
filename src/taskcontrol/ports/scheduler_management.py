"""The scheduler management port.

TaskControl does not activate recurring work. Cron does (ADR 0022). What TaskControl owns
is the *artefact* that tells cron what to run — writing it, proving it was written, and
removing it again.

This port is that contract, and it is deliberately narrow: **plan, apply, verify, remove,
status**. Everything specific to cron — block markers, file layout, the `crontab` command —
belongs to the adapter. A systemd-timer adapter would implement this same port.

Two rules shape every method here.

**Plan before apply.** An operator sees what will change before anything changes. This is
not a convenience; a tool that rewrites the crontab of a production host without showing
its work will not be trusted with the crontab of a production host.

**Verify by read-back.** Having written, read it back and compare. Writing successfully is
not evidence that the right thing is there — a file can land where cron ignores it, and a
crontab command can succeed against the wrong user's table.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable

from taskcontrol.domain.common.identifiers import TaskId
from taskcontrol.domain.deployment.strategies import DeploymentSpecification


class DeploymentChange(StrEnum):
    """What applying a plan entry would do to the host."""

    CREATE = "create"
    """No managed artefact exists for this task; one will be written."""

    UPDATE = "update"
    """A managed artefact exists and differs from what is desired."""

    REMOVE = "remove"
    """A managed artefact exists for a task that is no longer deployed."""

    UNCHANGED = "unchanged"
    """The host already matches. Applying does nothing at all."""

    @property
    def modifies_the_host(self) -> bool:
        """Whether applying this entry writes anything."""
        return self is not DeploymentChange.UNCHANGED


@dataclass(frozen=True, slots=True)
class DesiredArtefact:
    """One capability's activation intent, ready to be rendered.

    The adapter turns this into whatever its scheduler understands. It carries the task's
    identity rather than the whole revision, because rendering must not become a second
    place where execution semantics are decided.

    Attributes:
        task_id: The capability being deployed.
        slug: Its stable name, which becomes a filename or a block identifier.
        deployment: Where and in what shape the artefact goes.
        schedule: The cron expression, for strategies that carry their own schedule.
        command: The exact command line cron will run.
        content_digest: The revision digest, recorded in the artefact so drift between
            what is deployed and what was published can be detected by reading alone.
        description: A human-readable line, written into the artefact as a comment so an
            operator reading the crontab understands what they are looking at.
    """

    task_id: TaskId
    slug: str
    deployment: DeploymentSpecification
    command: str
    content_digest: str
    schedule: str | None = None
    description: str = ""


@dataclass(frozen=True, slots=True)
class PlanEntry:
    """One artefact's contribution to a plan.

    Attributes:
        task_id: The capability.
        slug: Its stable name, which is how the artefact is located on the host.
        change: What applying would do.
        target_description: Where the artefact lives, in terms an operator recognises —
            a path, or the name of a crontab.
        before: The current managed content, empty when there is none.
        after: The content that would be written, empty for a removal.
        detail: Why this entry says what it says, when that is not obvious.
        artefact: What is to be deployed, so applying needs no state carried over from
            planning. ``None`` for a removal, where there is nothing to deploy.
    """

    task_id: TaskId
    slug: str
    change: DeploymentChange
    target_description: str
    before: str = ""
    after: str = ""
    detail: str = ""
    artefact: DesiredArtefact | None = None


@dataclass(frozen=True, slots=True)
class DeploymentPlan:
    """What applying would do to the host, in full.

    Attributes:
        entries: One per capability considered, including unchanged ones. Unchanged
            entries are kept deliberately: "these forty are already correct" is part of
            what makes a plan trustworthy.
    """

    entries: tuple[PlanEntry, ...] = ()

    @property
    def is_empty(self) -> bool:
        """Whether applying this plan would change nothing."""
        return not any(entry.change.modifies_the_host for entry in self.entries)

    def entries_changing(self) -> tuple[PlanEntry, ...]:
        """Return only the entries that would modify the host."""
        return tuple(entry for entry in self.entries if entry.change.modifies_the_host)

    def count_of(self, change: DeploymentChange) -> int:
        """Return how many entries carry a given change.

        Args:
            change: The change to count.

        Returns:
            The count.
        """
        return sum(1 for entry in self.entries if entry.change is change)


@dataclass(frozen=True, slots=True)
class ApplyResult:
    """What applying actually did.

    Attributes:
        applied: Entries that were written and verified.
        rolled_back: Whether the host was restored because something failed.
        failure: What went wrong, when something did.
    """

    applied: tuple[PlanEntry, ...] = ()
    rolled_back: bool = False
    failure: str = ""

    @property
    def succeeded(self) -> bool:
        """Whether every entry was applied and verified."""
        return not self.failure and not self.rolled_back


class DriftKind(StrEnum):
    """How what is on the host differs from what TaskControl published."""

    MATCHES = "matches"
    """The host carries exactly what was published."""

    MISSING = "missing"
    """TaskControl expects a managed artefact and the host has none."""

    MODIFIED = "modified"
    """A managed artefact exists but its content differs — somebody edited it by hand."""

    UNEXPECTED = "unexpected"
    """A managed artefact exists for something TaskControl no longer deploys."""

    AMBIGUOUS = "ambiguous"
    """Managed identity could not be resolved: two regions claim the same task, a marker
    is malformed, or a file's name disagrees with its content.

    Never resolved by guessing. An adapter that guesses here will eventually delete
    somebody's unmanaged crontab entry.
    """


@dataclass(frozen=True, slots=True)
class VerificationFinding:
    """One discrepancy between the host and what was published.

    Attributes:
        task_id: The capability, when the finding can be attributed to one.
        kind: How it differs.
        target_description: Where, in terms an operator recognises.
        detail: What specifically differs.
    """

    kind: DriftKind
    target_description: str
    detail: str = ""
    task_id: TaskId | None = None


@dataclass(frozen=True, slots=True)
class VerificationReport:
    """The result of reading the host back and comparing.

    Attributes:
        findings: Every discrepancy found. Empty means the host matches.
        artefacts_checked: How many managed artefacts were examined, so an empty finding
            list can be distinguished from having looked at nothing.
    """

    findings: tuple[VerificationFinding, ...] = ()
    artefacts_checked: int = 0

    @property
    def matches(self) -> bool:
        """Whether the host carries exactly what was published."""
        return not self.findings


@dataclass(frozen=True, slots=True)
class SchedulerCapabilities:
    """What one scheduler adapter can actually do on this host.

    Reported rather than assumed, because the honest answer is host-specific: writing to
    ``/etc/cron.d`` needs privilege this process may not have, and saying so up front is
    better than failing halfway through an apply.

    Attributes:
        scheduler: What is being managed, for display. For example, ``"cron"``.
        writable_targets: Targets this process can actually write to right now.
        detail: Why a target is unavailable, when one is.
    """

    scheduler: str
    writable_targets: frozenset[str] = field(default_factory=frozenset)
    detail: str = ""


@runtime_checkable
class SchedulerManagement(Protocol):
    """Manages the artefacts that cause an external scheduler to activate work.

    An implementation must honour seven rules, which hold for every deployment strategy
    (ADR 0026):

    1. Unmanaged content is never modified — not reordered, not reformatted, not touched.
    2. Managed artefacts carry a stable identifier naming the task and its revision.
    3. Plan before apply.
    4. Verify by read-back.
    5. Fail closed on ambiguous identity. Never guess.
    6. Roll back a failed apply, restoring the previous state exactly.
    7. Rendering is deterministic: the same revision renders byte-identically every time.
    """

    def capabilities(self) -> SchedulerCapabilities:
        """Report what this adapter can do on this host.

        Returns:
            The capabilities, including which targets are writable now.
        """
        ...

    def plan(self, desired: Sequence[DesiredArtefact]) -> DeploymentPlan:
        """Compute what applying ``desired`` would change, without changing anything.

        Args:
            desired: The complete set of artefacts that should exist. Anything managed and
                absent from this sequence is planned for removal, which is what makes the
                plan a statement about the whole managed estate rather than a diff.

        Returns:
            The plan, including unchanged entries.

        Raises:
            Exception: If managed identity on the host is ambiguous. A plan computed from
                an ambiguous host would propose the wrong changes.
        """
        ...

    def apply(self, plan: DeploymentPlan) -> ApplyResult:
        """Apply a plan, verifying each write by reading it back.

        On any failure the host is restored to its previous state. A partially applied
        deployment is the one outcome that must not be left behind, because it is the one
        an operator cannot reason about.

        Args:
            plan: A plan produced by :meth:`plan`.

        Returns:
            What was applied, and whether a rollback occurred.
        """
        ...

    def verify(self, desired: Sequence[DesiredArtefact]) -> VerificationReport:
        """Read the host and report how it differs from what was published.

        This is how hand-edited crontabs are found. It reads only.

        Args:
            desired: The artefacts that should exist.

        Returns:
            The report. Empty findings means the host matches.
        """
        ...

    def remove(self, task_ids: Sequence[TaskId]) -> ApplyResult:
        """Remove managed artefacts for the given capabilities.

        Removal is by managed identity alone. An adapter must never remove content it did
        not write, however much it resembles something it would have written.

        Args:
            task_ids: The capabilities to undeploy.

        Returns:
            What was removed.
        """
        ...
