"""Durable claims, against a real database.

R1 measured what the absence of these costs: two concurrent activations of one task, both
running, neither blocked, with the forbid-overlap policy in force. These tests are the
evidence that the replacement actually holds — so they run against every backend the
product supports, because "at most one" is a database guarantee and not a Python one.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from taskcontrol.adapters.locking.durable import DurableOverlapLock
from taskcontrol.adapters.persistence.claim_store import SqlAlchemyClaimStore
from taskcontrol.adapters.persistence.unit_of_work import UnitOfWork
from taskcontrol.common.errors import TransientInfrastructureError, ValidationError
from taskcontrol.domain.claims.claim import Claim, ClaimSubject, FencingToken
from taskcontrol.domain.common.identifiers import TaskId
from taskcontrol.domain.common.values import Duration, UtcTimestamp
from taskcontrol.infrastructure.database import create_database_engine, create_session_factory
from taskcontrol.ports.claims import ClaimNotHeldError, ClaimStore
from taskcontrol.ports.lock import LockNotAcquiredError, OverlapLock

LEASE = Duration(60)
START = UtcTimestamp(datetime(2026, 7, 27, 2, 0, tzinfo=UTC))


class MovableClock:
    """A clock a test can push forward, so lease expiry needs no waiting."""

    def __init__(self, now: UtcTimestamp = START) -> None:
        self._now = now

    def now(self) -> UtcTimestamp:
        return self._now

    def monotonic(self) -> float:
        return self._now.value.timestamp()

    def advance(self, seconds: int) -> None:
        """Move time forward."""
        self._now = UtcTimestamp(self._now.value + timedelta(seconds=seconds))


@pytest.fixture
def clock() -> MovableClock:
    return MovableClock()


@pytest.fixture
def claims(session_factory, clock: MovableClock) -> SqlAlchemyClaimStore:
    return SqlAlchemyClaimStore(session_factory, clock)


SUBJECT = ClaimSubject("task:0193-aaaa")


class TestExclusivity:
    def test_satisfies_the_port(self, claims: SqlAlchemyClaimStore) -> None:
        assert isinstance(claims, ClaimStore)

    def test_one_owner_gets_the_claim(self, claims: SqlAlchemyClaimStore) -> None:
        assert claims.try_acquire(SUBJECT, owner="host-a:1", lease=LEASE) is not None

    def test_a_second_owner_is_refused(self, claims: SqlAlchemyClaimStore) -> None:
        """The guarantee the whole design exists for."""
        claims.try_acquire(SUBJECT, owner="host-a:1", lease=LEASE)
        assert claims.try_acquire(SUBJECT, owner="host-b:2", lease=LEASE) is None

    def test_the_same_owner_in_a_second_process_is_also_refused(
        self, claims: SqlAlchemyClaimStore
    ) -> None:
        """Identity is not permission. A live claim refuses everyone, including its holder.

        Under cron, the same task activating twice presents plausibly similar identities.
        Treating a matching owner as re-entrancy would let exactly the overlap this
        prevents straight through.
        """
        claims.try_acquire(SUBJECT, owner="host-a:1", lease=LEASE)
        assert claims.try_acquire(SUBJECT, owner="host-a:1", lease=LEASE) is None

    def test_different_subjects_do_not_contend(self, claims: SqlAlchemyClaimStore) -> None:
        assert claims.try_acquire(ClaimSubject("task:one"), owner="a", lease=LEASE)
        assert claims.try_acquire(ClaimSubject("task:two"), owner="b", lease=LEASE)


class TestDurability:
    def test_a_claim_survives_the_process_that_took_it(
        self, session_factory, clock: MovableClock
    ) -> None:
        """The point of durability: a second process sees the first one's claim.

        Two stores over one database stand in for two processes, which is exactly what two
        cron activations are.
        """
        first = SqlAlchemyClaimStore(session_factory, clock)
        second = SqlAlchemyClaimStore(session_factory, clock)

        assert first.try_acquire(SUBJECT, owner="host-a:1", lease=LEASE) is not None
        assert second.try_acquire(SUBJECT, owner="host-b:2", lease=LEASE) is None


class TestExpiry:
    def test_a_lapsed_claim_can_be_taken_over(
        self, claims: SqlAlchemyClaimStore, clock: MovableClock
    ) -> None:
        """A dead owner must never block a subject forever."""
        claims.try_acquire(SUBJECT, owner="dead-host:1", lease=LEASE)
        clock.advance(LEASE.to_primitive() + 1)

        assert claims.try_acquire(SUBJECT, owner="live-host:2", lease=LEASE) is not None

    def test_take_over_happens_without_a_reaper(
        self, claims: SqlAlchemyClaimStore, clock: MovableClock
    ) -> None:
        """Recovery must not depend on a cleanup process that may also be down."""
        claims.try_acquire(SUBJECT, owner="dead-host:1", lease=LEASE)
        clock.advance(LEASE.to_primitive() + 1)

        assert claims.current(SUBJECT) is None
        assert claims.try_acquire(SUBJECT, owner="live-host:2", lease=LEASE) is not None

    def test_a_live_claim_is_not_taken_over(
        self, claims: SqlAlchemyClaimStore, clock: MovableClock
    ) -> None:
        claims.try_acquire(SUBJECT, owner="host-a:1", lease=LEASE)
        clock.advance(LEASE.to_primitive() - 1)

        assert claims.try_acquire(SUBJECT, owner="host-b:2", lease=LEASE) is None


class TestFencing:
    def test_each_acquisition_gets_a_higher_token(
        self, claims: SqlAlchemyClaimStore, clock: MovableClock
    ) -> None:
        """Monotonic across owners, which is what lets a stalled owner detect supersession."""
        first = claims.try_acquire(SUBJECT, owner="host-a:1", lease=LEASE)
        clock.advance(LEASE.to_primitive() + 1)
        second = claims.try_acquire(SUBJECT, owner="host-b:2", lease=LEASE)

        assert first is not None and second is not None
        assert second.fencing_token.supersedes(first.fencing_token)

    def test_releasing_does_not_restart_the_token(self, claims: SqlAlchemyClaimStore) -> None:
        """A released claim must not let the next holder reuse a token already issued.

        If it did, a stalled owner holding token 2 would find the subject back at token 2
        and conclude it was still current.
        """
        first = claims.try_acquire(SUBJECT, owner="host-a:1", lease=LEASE)
        assert first is not None
        claims.release(first)

        second = claims.try_acquire(SUBJECT, owner="host-b:2", lease=LEASE)
        assert second is not None
        assert second.fencing_token.supersedes(first.fencing_token)

    def test_a_superseded_owner_cannot_renew(
        self, claims: SqlAlchemyClaimStore, clock: MovableClock
    ) -> None:
        """The stalled-owner case: it wakes, tries to renew, and is told it lost the claim."""
        stalled = claims.try_acquire(SUBJECT, owner="host-a:1", lease=LEASE)
        assert stalled is not None
        clock.advance(LEASE.to_primitive() + 1)
        claims.try_acquire(SUBJECT, owner="host-b:2", lease=LEASE)

        with pytest.raises(ClaimNotHeldError):
            claims.renew(stalled, lease=LEASE)

    def test_a_superseded_owner_cannot_release_the_new_claim(
        self, claims: SqlAlchemyClaimStore, clock: MovableClock
    ) -> None:
        """Cleaning up after a crash must never lapse the claim that replaced yours."""
        stalled = claims.try_acquire(SUBJECT, owner="host-a:1", lease=LEASE)
        assert stalled is not None
        clock.advance(LEASE.to_primitive() + 1)
        successor = claims.try_acquire(SUBJECT, owner="host-b:2", lease=LEASE)

        claims.release(stalled)

        live = claims.current(SUBJECT)
        assert live is not None
        assert successor is not None
        assert live.owner == successor.owner


class TestRenewal:
    def test_renewing_extends_the_lease(
        self, claims: SqlAlchemyClaimStore, clock: MovableClock
    ) -> None:
        claim = claims.try_acquire(SUBJECT, owner="host-a:1", lease=LEASE)
        assert claim is not None
        clock.advance(30)

        renewed = claims.renew(claim, lease=LEASE)
        clock.advance(40)

        assert claims.current(SUBJECT) is not None
        assert renewed.fencing_token == claim.fencing_token

    def test_renewing_a_lapsed_claim_raises(
        self, claims: SqlAlchemyClaimStore, clock: MovableClock
    ) -> None:
        claim = claims.try_acquire(SUBJECT, owner="host-a:1", lease=LEASE)
        assert claim is not None
        clock.advance(LEASE.to_primitive() + 1)

        with pytest.raises(ClaimNotHeldError):
            claims.renew(claim, lease=LEASE)


class TestRelease:
    def test_releasing_frees_the_subject(self, claims: SqlAlchemyClaimStore) -> None:
        claim = claims.try_acquire(SUBJECT, owner="host-a:1", lease=LEASE)
        assert claim is not None
        claims.release(claim)

        assert claims.try_acquire(SUBJECT, owner="host-b:2", lease=LEASE) is not None

    def test_releasing_twice_does_not_raise(self, claims: SqlAlchemyClaimStore) -> None:
        claim = claims.try_acquire(SUBJECT, owner="host-a:1", lease=LEASE)
        assert claim is not None
        claims.release(claim)
        claims.release(claim)

    def test_releasing_a_claim_that_was_never_taken_does_not_raise(
        self, claims: SqlAlchemyClaimStore
    ) -> None:
        """A process cleaning up after a crash must be able to call this safely."""
        claims.release(
            Claim(
                subject=ClaimSubject("task:never-claimed"),
                owner="ghost",
                acquired_at=START,
                expires_at=UtcTimestamp(START.value + timedelta(seconds=60)),
                fencing_token=FencingToken(1),
            )
        )


class TestUnreachableStore:
    def test_acquisition_fails_rather_than_being_assumed(self, clock: MovableClock) -> None:
        """The rule that matters most.

        Treating "I could not check" as "nobody else has it" is how two backups end up
        running against one database at the same time. Acquisition must raise, and the
        runtime records a condition error rather than reading silence as permission.
        """
        unreachable = create_database_engine("sqlite+pysqlite:////nonexistent/claims.db")
        store = SqlAlchemyClaimStore(create_session_factory(unreachable), clock)

        with pytest.raises(TransientInfrastructureError):
            store.try_acquire(SUBJECT, owner="host-a:1", lease=LEASE)

    def test_the_failure_does_not_leak_vendor_internals(self, clock: MovableClock) -> None:
        """An operator sees what went wrong, not a SQLAlchemy traceback (R1 Finding 3)."""
        unreachable = create_database_engine("sqlite+pysqlite:////nonexistent/claims.db")
        store = SqlAlchemyClaimStore(create_session_factory(unreachable), clock)

        with pytest.raises(TransientInfrastructureError) as raised:
            store.try_acquire(SUBJECT, owner="host-a:1", lease=LEASE)

        message = str(raised.value)
        assert "sqlite3" not in message
        assert "OperationalError" not in message


class TestDurableOverlapLock:
    def test_satisfies_the_port(self, claims: SqlAlchemyClaimStore) -> None:
        assert isinstance(DurableOverlapLock(claims), OverlapLock)

    def test_a_second_activation_is_refused(self, claims: SqlAlchemyClaimStore) -> None:
        """The R1 finding, now the other way round: the second activation does not run."""
        lock = DurableOverlapLock(claims)
        task_id = TaskId.generate()

        assert lock.try_acquire(task_id, owner="cron-a") is not None
        assert lock.try_acquire(task_id, owner="cron-b") is None

    def test_two_processes_do_not_share_a_lock_in_memory(
        self, session_factory, clock: MovableClock
    ) -> None:
        """Two lock instances, as two cron activations would be. Only one may proceed."""
        task_id = TaskId.generate()
        first = DurableOverlapLock(SqlAlchemyClaimStore(session_factory, clock))
        second = DurableOverlapLock(SqlAlchemyClaimStore(session_factory, clock))

        assert first.try_acquire(task_id, owner="cron-a") is not None
        assert second.try_acquire(task_id, owner="cron-b") is None

    def test_releasing_frees_the_capability(self, claims: SqlAlchemyClaimStore) -> None:
        lock = DurableOverlapLock(claims)
        task_id = TaskId.generate()

        handle = lock.try_acquire(task_id, owner="cron-a")
        assert handle is not None
        lock.release(handle)

        assert lock.try_acquire(task_id, owner="cron-b") is not None

    def test_hold_releases_even_when_the_block_raises(self, claims: SqlAlchemyClaimStore) -> None:
        lock = DurableOverlapLock(claims)
        task_id = TaskId.generate()

        with pytest.raises(RuntimeError), lock.hold(task_id, owner="cron-a"):
            raise RuntimeError("the work failed")

        assert lock.try_acquire(task_id, owner="cron-b") is not None

    def test_hold_raises_when_another_activation_holds_it(
        self, claims: SqlAlchemyClaimStore
    ) -> None:
        lock = DurableOverlapLock(claims)
        task_id = TaskId.generate()
        lock.try_acquire(task_id, owner="cron-a")

        with pytest.raises(LockNotAcquiredError), lock.hold(task_id, owner="cron-b"):
            pass

    def test_the_scope_description_does_not_overclaim(self, claims: SqlAlchemyClaimStore) -> None:
        """A lock that claims more than it delivers is worse than no lock."""
        description = DurableOverlapLock(claims).scope_description
        assert "database" in description
        assert "lease" in description


def test_a_claim_must_expire() -> None:
    """A claim that could not expire would make a dead process's subject unusable."""
    with pytest.raises(ValidationError):
        Claim(
            subject=SUBJECT,
            owner="host-a:1",
            acquired_at=START,
            expires_at=START,
            fencing_token=FencingToken(1),
        )


def test_renewal_may_not_shorten_a_lease() -> None:
    """Shortening by renewing is always a mistake, and a silent one."""
    claim = Claim(
        subject=SUBJECT,
        owner="host-a:1",
        acquired_at=START,
        expires_at=UtcTimestamp(START.value + timedelta(seconds=60)),
        fencing_token=FencingToken(1),
    )
    with pytest.raises(ValidationError):
        claim.renewed_until(UtcTimestamp(START.value + timedelta(seconds=30)))


class TestInvariantsThatLookLikeCleanupOpportunities:
    """Two properties a future refactor could remove while appearing to tidy up.

    Both are load-bearing, both are non-obvious from the code that depends on them, and
    neither fails visibly when broken — the damage shows up as two runs of one capability
    during an incident. They are asserted here by name so that removing them breaks a test
    that says why.
    """

    def test_a_released_and_reacquired_subject_never_reissues_a_token(
        self, claims: SqlAlchemyClaimStore
    ) -> None:
        """Deleting released rows would create an ABA ownership problem.

        A stalled owner holding token 2 would find the subject recycled back to token 2
        under a new holder and conclude its own authority was still current. Lapsing the
        row instead of deleting it is what makes the token strictly monotonic per subject
        for the life of the database.
        """
        tokens = []
        for owner in ("host-a:1", "host-b:2", "host-c:3"):
            claim = claims.try_acquire(SUBJECT, owner=owner, lease=LEASE)
            assert claim is not None
            tokens.append(claim.fencing_token.to_primitive())
            claims.release(claim)

        assert tokens == sorted(set(tokens))
        assert len(tokens) == len(set(tokens))

    def test_a_claim_survives_a_business_transaction_rollback(
        self, session_factory, clock: MovableClock
    ) -> None:
        """The claim store must not join the caller's unit of work.

        If it did, a rollback would erase the protection while the work it protected had
        already started — and the claim would be invisible to other processes until
        commit, which is precisely when it needs to be visible.
        """
        claims = SqlAlchemyClaimStore(session_factory, clock)

        with pytest.raises(RuntimeError), UnitOfWork(session_factory) as uow:
            assert claims.try_acquire(SUBJECT, owner="host-a:1", lease=LEASE) is not None
            uow.tasks.list_tasks(limit=1)
            raise RuntimeError("the business transaction fails after the claim was taken")

        # The transaction rolled back. The claim did not.
        assert claims.current(SUBJECT) is not None
        assert claims.try_acquire(SUBJECT, owner="host-b:2", lease=LEASE) is None
