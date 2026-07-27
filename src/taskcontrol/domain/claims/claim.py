"""A claim: durable, time-bounded ownership of a named subject by a named owner.

One primitive serves two jobs (ADR 0023). Before a cron-activated wrapper runs it claims
``task:<id>``, which is how overlap is actually prevented across processes. Before a worker
processes queued work it claims ``work-item:<id>``. Same ownership rules, same expiry, same
recovery — an operator learns one model, and an incident has one thing to reason about.

Three properties carry the weight:

**Expiry.** Every claim ends. A process killed mid-run must not block its task forever, and
no operator should have to know where to go to clear a stuck lock.

**Owner identity.** A claim records who holds it, so a stale handle cannot release somebody
else's claim — which is exactly what a resumed process would otherwise do.

**Fencing.** A monotonic token, so an owner that stalls past its expiry and then wakes up
can tell that it no longer holds what it thinks it holds. Without this, expiry alone lets
two processes believe they own the same subject at the same instant.

This module is pure. Acquiring, renewing, and releasing live behind
:class:`~taskcontrol.ports.claims.ClaimStore`, because durability is an infrastructure
property and the domain must not assume how it is achieved.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self

from taskcontrol.common.errors import ValidationError
from taskcontrol.domain.common.identifiers import TaskId
from taskcontrol.domain.common.values import Duration, UtcTimestamp

MAX_SUBJECT_LENGTH = 200
MAX_OWNER_LENGTH = 200

TASK_SUBJECT_PREFIX = "task"
WORK_ITEM_SUBJECT_PREFIX = "work-item"


@dataclass(frozen=True, slots=True)
class ClaimSubject:
    """What is claimed.

    An opaque key to the store, and deliberately so: the store enforces exclusivity without
    knowing whether it is protecting a scheduled task or a queued work item. The prefixes
    exist for humans reading a diagnostic, not for the store to branch on.

    Attributes:
        key: The subject key, such as ``task:0193...``.
    """

    key: str

    def __post_init__(self) -> None:
        """Validate the key.

        Raises:
            ValidationError: If the key is empty or too long.
        """
        if not isinstance(self.key, str) or not self.key.strip():
            raise ValidationError("A claim subject must not be empty.")
        if len(self.key) > MAX_SUBJECT_LENGTH:
            raise ValidationError(
                "Claim subject is too long.", details={"maximum": MAX_SUBJECT_LENGTH}
            )

    @classmethod
    def for_task(cls, task_id: TaskId) -> Self:
        """Return the subject protecting one capability against overlapping runs."""
        return cls(f"{TASK_SUBJECT_PREFIX}:{task_id.to_primitive()}")

    @classmethod
    def for_work_item(cls, work_item_id: str) -> Self:
        """Return the subject protecting one queued work item against double processing."""
        return cls(f"{WORK_ITEM_SUBJECT_PREFIX}:{work_item_id}")

    def to_primitive(self) -> str:
        """Return the key."""
        return self.key

    def __str__(self) -> str:
        """Return the key."""
        return self.key


@dataclass(frozen=True, slots=True, order=True)
class FencingToken:
    """A monotonic token proving which acquisition of a subject a holder belongs to.

    Expiry alone is not enough. An owner can stall — a long GC pause, a suspended VM, a
    blocked write — past its lease, have the subject reclaimed by somebody else, and then
    wake up still believing it holds the claim. Both would act at once.

    The token closes that: it increases on every acquisition of a subject, so an owner
    holding token 7 against a subject now at token 8 can tell it has been superseded,
    without needing to have noticed the moment it happened.

    Attributes:
        value: The token. Increases with every acquisition of its subject.
    """

    value: int

    def __post_init__(self) -> None:
        """Validate the token.

        Raises:
            ValidationError: If the token is not positive.
        """
        if not isinstance(self.value, int) or isinstance(self.value, bool) or self.value < 1:
            raise ValidationError(
                "A fencing token must be a positive integer.", details={"value": self.value}
            )

    def supersedes(self, other: FencingToken) -> bool:
        """Whether this token is from a later acquisition than ``other``."""
        return self.value > other.value

    def to_primitive(self) -> int:
        """Return the token value."""
        return self.value

    def __str__(self) -> str:
        """Return the token value as text."""
        return str(self.value)


@dataclass(frozen=True, slots=True)
class Claim:
    """Durable, time-bounded ownership of a subject.

    Attributes:
        subject: What is held.
        owner: Who holds it. Recorded explicitly so a stale handle cannot release somebody
            else's claim.
        acquired_at: When it was taken.
        expires_at: When it lapses if not renewed. Never absent: a claim that could not
            expire would make a dead process's subject permanently unusable.
        fencing_token: Which acquisition of the subject this is.
    """

    subject: ClaimSubject
    owner: str
    acquired_at: UtcTimestamp
    expires_at: UtcTimestamp
    fencing_token: FencingToken

    def __post_init__(self) -> None:
        """Validate the claim.

        Raises:
            ValidationError: If the owner is unusable or the lease ends before it began.
        """
        if not isinstance(self.owner, str) or not self.owner.strip():
            raise ValidationError(
                "A claim must record who holds it. An anonymous claim cannot be safely "
                "released or renewed."
            )
        if len(self.owner) > MAX_OWNER_LENGTH:
            raise ValidationError("Claim owner is too long.", details={"maximum": MAX_OWNER_LENGTH})
        if self.expires_at.value <= self.acquired_at.value:
            raise ValidationError(
                "A claim must expire after it was acquired.",
                details={
                    "acquired_at": self.acquired_at.to_primitive(),
                    "expires_at": self.expires_at.to_primitive(),
                },
            )

    def has_expired_at(self, moment: UtcTimestamp) -> bool:
        """Whether this claim has lapsed by ``moment``.

        Args:
            moment: The instant to judge against.

        Returns:
            ``True`` when the lease has ended, which makes the subject claimable again.
        """
        return moment.value >= self.expires_at.value

    def renewed_until(self, expires_at: UtcTimestamp) -> Self:
        """Return this claim with a later expiry.

        Renewal never changes the fencing token: it is the same acquisition, held longer.
        Issuing a new token here would invalidate the holder's own token mid-run.

        Args:
            expires_at: The new expiry.

        Returns:
            The renewed claim.

        Raises:
            ValidationError: If the new expiry is not later than the current one. Shortening
                a lease by renewing it is always a mistake, and a silent one.
        """
        if expires_at.value <= self.expires_at.value:
            raise ValidationError(
                "Renewing a claim must extend it. A renewal that shortened the lease would "
                "make the subject reclaimable sooner than its holder expects.",
                details={
                    "current_expiry": self.expires_at.to_primitive(),
                    "requested_expiry": expires_at.to_primitive(),
                },
            )
        return type(self)(
            subject=self.subject,
            owner=self.owner,
            acquired_at=self.acquired_at,
            expires_at=expires_at,
            fencing_token=self.fencing_token,
        )

    def is_held_by(self, owner: str) -> bool:
        """Whether ``owner`` is this claim's holder."""
        return self.owner == owner

    def remaining_at(self, moment: UtcTimestamp) -> Duration:
        """Return how much lease is left at ``moment``, floored at zero.

        Args:
            moment: The instant to measure from.

        Returns:
            The remaining lease.
        """
        seconds = (self.expires_at.value - moment.value).total_seconds()
        return Duration(max(0, int(seconds)))

    def to_primitive(self) -> dict[str, Any]:
        """Return a stable representation, for diagnostics and the local journal."""
        return {
            "subject": self.subject.to_primitive(),
            "owner": self.owner,
            "acquired_at": self.acquired_at.to_primitive(),
            "expires_at": self.expires_at.to_primitive(),
            "fencing_token": self.fencing_token.to_primitive(),
        }
