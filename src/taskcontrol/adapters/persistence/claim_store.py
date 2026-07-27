"""The durable claim store, backed by a relational database.

This is the adapter that makes overlap protection real across processes (ADR 0023). R1
measured what its absence costs: two cron activations of one task, both running, neither
blocked, with the forbid-overlap policy in force.

Three design points are worth reading before changing anything here.

**It owns its own transaction.** Every operation commits immediately, in a session of its
own, deliberately not the caller's unit of work. A claim taken inside a business
transaction would vanish on rollback while the work it was protecting had already started,
and would be invisible to other processes until commit — which is precisely when it needs
to be visible.

**Rows are never deleted.** Releasing lapses a claim by setting its expiry to now. Deleting
would restart the fencing token, and a stalled owner holding token 7 would find the subject
back at token 1 and conclude it was still current.

**Taking over an expired claim happens here, not in a reaper.** Recovery that depends on a
cleanup process running is recovery that fails exactly when that process is also down.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from taskcontrol.adapters.persistence.mappers import from_naive_utc, to_naive_utc
from taskcontrol.adapters.persistence.models import ClaimRecord
from taskcontrol.common.errors import TransientInfrastructureError
from taskcontrol.domain.claims.claim import Claim, ClaimSubject, FencingToken
from taskcontrol.domain.common.values import Duration, UtcTimestamp
from taskcontrol.ports.claims import ClaimNotHeldError
from taskcontrol.ports.clock import Clock


class SqlAlchemyClaimStore:
    """Durable claims in a relational database.

    Args:
        session_factory: Makes the short-lived sessions this store commits through.
        clock: Supplies the current instant. Injected so expiry can be tested without
            waiting, and so every timestamp in the system comes from one place.
    """

    def __init__(self, session_factory: sessionmaker[Session], clock: Clock) -> None:
        """Store the collaborators."""
        self._session_factory = session_factory
        self._clock = clock

    def try_acquire(self, subject: ClaimSubject, *, owner: str, lease: Duration) -> Claim | None:
        """Take a claim, or return ``None`` when somebody else holds a live one.

        Raises:
            TransientInfrastructureError: If the store cannot be reached. Acquisition
                fails; it is never assumed. Code that treats "I could not check" as
                "nobody else has it" is how two backups run against one database.
        """
        now = self._clock.now()
        expires_at = _add(now, lease)

        try:
            with self._session_factory() as session:
                claimed = self._insert_or_take_over(session, subject, owner, now, expires_at)
                session.commit()
                return claimed
        except SQLAlchemyError as error:
            raise TransientInfrastructureError(
                "Could not reach the claim store, so it is not known whether this "
                "capability is already running. Refusing to start rather than risk two "
                "runs at once.",
                details={"subject": subject.to_primitive(), "owner": owner},
            ) from error

    def _insert_or_take_over(
        self,
        session: Session,
        subject: ClaimSubject,
        owner: str,
        now: UtcTimestamp,
        expires_at: UtcTimestamp,
    ) -> Claim | None:
        """Insert a new claim, or take over one that has lapsed.

        Both paths are atomic against a concurrent claimer: the insert is guarded by the
        primary key, and the take-over is a conditional update that only one racer's
        statement can match.
        """
        record = session.get(ClaimRecord, subject.to_primitive())

        if record is None:
            session.add(
                ClaimRecord(
                    subject=subject.to_primitive(),
                    owner=owner,
                    acquired_at=to_naive_utc(now),
                    expires_at=to_naive_utc(expires_at),
                    fencing_token=1,
                )
            )
            try:
                session.flush()
            except IntegrityError:
                # Somebody inserted the same subject between the read and the flush. Their
                # claim is live, so ours is refused — which is the correct answer.
                session.rollback()
                return None
            return Claim(
                subject=subject,
                owner=owner,
                acquired_at=now,
                expires_at=expires_at,
                fencing_token=FencingToken(1),
            )

        next_token = record.fencing_token + 1
        taken_over = _rows_affected(
            session.execute(
                update(ClaimRecord)
                .where(
                    ClaimRecord.subject == subject.to_primitive(),
                    # The whole race is decided by this predicate. A live claim fails to match,
                    # and of two processes taking over the same lapsed claim only one updates.
                    ClaimRecord.expires_at <= to_naive_utc(now),
                    ClaimRecord.fencing_token == record.fencing_token,
                )
                .values(
                    owner=owner,
                    acquired_at=to_naive_utc(now),
                    expires_at=to_naive_utc(expires_at),
                    fencing_token=next_token,
                )
            )
        )

        if taken_over != 1:
            return None

        return Claim(
            subject=subject,
            owner=owner,
            acquired_at=now,
            expires_at=expires_at,
            fencing_token=FencingToken(next_token),
        )

    def renew(self, claim: Claim, *, lease: Duration) -> Claim:
        """Extend a held claim.

        Raises:
            ClaimNotHeldError: If the claim lapsed or somebody else now holds it. The
                caller's work is no longer protected and it must act on that.
            TransientInfrastructureError: If the store cannot be reached.
        """
        now = self._clock.now()
        expires_at = _add(now, lease)

        try:
            with self._session_factory() as session:
                renewed = _rows_affected(
                    session.execute(
                        update(ClaimRecord)
                        .where(
                            ClaimRecord.subject == claim.subject.to_primitive(),
                            ClaimRecord.owner == claim.owner,
                            # The fencing token is what makes this safe. Matching on owner
                            # alone would let a process renew a claim it lost and reacquired
                            # under a later token, hiding the fact that it was superseded.
                            ClaimRecord.fencing_token == claim.fencing_token.to_primitive(),
                            ClaimRecord.expires_at > to_naive_utc(now),
                        )
                        .values(expires_at=to_naive_utc(expires_at))
                    )
                )
                session.commit()

                if renewed != 1:
                    raise ClaimNotHeldError(
                        f"The claim on {claim.subject} is no longer held by {claim.owner}. "
                        "It lapsed, or another process has taken it over."
                    )
        except SQLAlchemyError as error:
            raise TransientInfrastructureError(
                "Could not reach the claim store to renew a claim.",
                details={"subject": claim.subject.to_primitive()},
            ) from error

        return claim.renewed_until(expires_at)

    def release(self, claim: Claim) -> None:
        """Release a claim by lapsing it.

        Never raises for a claim that has already lapsed or been taken over. A process
        cleaning up after a crash must be able to call this safely, and it must never
        lapse the claim that superseded its own — which is what the fencing token in the
        predicate prevents.

        Raises:
            TransientInfrastructureError: If the store cannot be reached.
        """
        now = self._clock.now()
        try:
            with self._session_factory() as session:
                session.execute(
                    update(ClaimRecord)
                    .where(
                        ClaimRecord.subject == claim.subject.to_primitive(),
                        ClaimRecord.owner == claim.owner,
                        ClaimRecord.fencing_token == claim.fencing_token.to_primitive(),
                    )
                    .values(expires_at=to_naive_utc(now))
                )
                session.commit()
        except SQLAlchemyError as error:
            raise TransientInfrastructureError(
                "Could not reach the claim store to release a claim. It will lapse on its "
                "own when the lease expires.",
                details={"subject": claim.subject.to_primitive()},
            ) from error

    def current(self, subject: ClaimSubject) -> Claim | None:
        """Return the live claim on a subject, for diagnostics only.

        Raises:
            TransientInfrastructureError: If the store cannot be reached.
        """
        now = self._clock.now()
        try:
            with self._session_factory() as session:
                record = session.scalar(
                    select(ClaimRecord).where(ClaimRecord.subject == subject.to_primitive())
                )
                if record is None:
                    return None
                claim = _to_claim(record)
        except SQLAlchemyError as error:
            raise TransientInfrastructureError(
                "Could not reach the claim store.",
                details={"subject": subject.to_primitive()},
            ) from error

        return None if claim.has_expired_at(now) else claim


def _rows_affected(result: Any) -> int:
    """Return how many rows a statement changed.

    The row count is the whole answer to "did I win the race?", so it is read through one
    place rather than being reached for ad hoc.
    """
    return cast("CursorResult[Any]", result).rowcount


def _to_claim(record: ClaimRecord) -> Claim:
    """Build a domain claim from a stored record."""
    acquired_at = from_naive_utc(record.acquired_at)
    expires_at = from_naive_utc(record.expires_at)
    assert acquired_at is not None and expires_at is not None  # noqa: S101 - both are NOT NULL
    return Claim(
        subject=ClaimSubject(record.subject),
        owner=record.owner,
        acquired_at=acquired_at,
        expires_at=expires_at,
        fencing_token=FencingToken(record.fencing_token),
    )


def _add(moment: UtcTimestamp, lease: Duration) -> UtcTimestamp:
    """Return the instant a lease starting now would end."""
    return UtcTimestamp(moment.value + timedelta(seconds=lease.to_primitive()))
