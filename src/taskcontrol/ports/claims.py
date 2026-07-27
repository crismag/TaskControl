"""The claim store port.

Durability is an infrastructure property, so the domain describes what a claim *is* and
this port describes what can be done with one. An implementation must survive the death of
the claiming process — which rules out anything held in memory, and is the whole reason
ADR 0023 exists.

**The rule that matters most: an unreachable store fails acquisition.** It never assumes.
A claim that cannot be verified is not held, and code that treats "I could not check" as
"nobody else has it" is how two backups run against one database at the same time.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from taskcontrol.domain.claims.claim import Claim, ClaimSubject
from taskcontrol.domain.common.values import Duration


class ClaimNotHeldError(Exception):
    """Raised when renewing or releasing a claim its supposed owner does not hold.

    Usually means the lease expired and somebody else took the subject — the case fencing
    tokens exist for. A plain exception rather than a TaskControl error: callers translate
    it into their own vocabulary, and the port stays free of outcome semantics.
    """


@runtime_checkable
class ClaimStore(Protocol):
    """Durable, time-bounded ownership of named subjects.

    An implementation must guarantee:

    * **Durability.** A claim survives the death of the process that took it.
    * **Exclusivity.** At most one live claim per subject, enforced by the store rather
      than by callers agreeing to behave.
    * **Expiry.** Every claim lapses. A dead owner never blocks a subject forever.
    * **Monotonic fencing.** Each acquisition of a subject gets a strictly higher token
      than the last, so a stalled owner can discover it was superseded.
    * **Verifiability.** If the store cannot be reached, acquisition fails.
    """

    def try_acquire(self, subject: ClaimSubject, *, owner: str, lease: Duration) -> Claim | None:
        """Take a claim on a subject, without waiting.

        Never blocks. Work that cannot start now is recorded and explained rather than
        queued behind a lock while its schedule moves on.

        An expired claim held by somebody else must be taken over here, not left to a
        separate reaper: recovery that depends on a cleanup process running is recovery
        that fails exactly when that process is also down.

        Args:
            subject: What to claim.
            owner: Who is claiming it. Must identify the holder well enough that a
                different process cannot accidentally present the same identity.
            lease: How long the claim lasts unless renewed.

        Returns:
            The claim, or ``None`` when a live claim is already held by somebody else.

        Raises:
            Exception: If the store cannot be reached. Never assume acquisition.
        """
        ...

    def renew(self, claim: Claim, *, lease: Duration) -> Claim:
        """Extend a held claim's lease.

        Args:
            claim: The claim to extend.
            lease: How much longer it should last, measured from now.

        Returns:
            The renewed claim, carrying the same fencing token — it is the same
            acquisition, held longer.

        Raises:
            ClaimNotHeldError: If the claim has lapsed or is now held by somebody else.
                The caller must treat its work as no longer protected.
            Exception: If the store cannot be reached.
        """
        ...

    def release(self, claim: Claim) -> None:
        """Release a held claim.

        Releasing a claim that has already lapsed, or that somebody else now holds, must
        not raise: a process cleaning up after a crash should be able to call this safely,
        and it must never delete the claim that superseded its own.

        Args:
            claim: The claim to release.
        """
        ...

    def current(self, subject: ClaimSubject) -> Claim | None:
        """Return the live claim on a subject, if there is one.

        For diagnostics only. Never use this to decide whether to acquire — the gap between
        checking and acquiring is a race, and :meth:`try_acquire` exists precisely so that
        decision happens in one atomic step.

        Args:
            subject: What to inspect.

        Returns:
            The live claim, or ``None`` when the subject is free or its claim has lapsed.
        """
        ...
