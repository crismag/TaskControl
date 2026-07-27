# ADR 0023: Overlap Leases and Queue Claims Are One Capability

- Document level: **1 — Architecture**
- Lifecycle state: Canonical
- Status: Accepted
- Date: 2026-07-27
- Owners: TaskControl maintainers
- Supersedes: ADR 0021 (Overlap Locking Is Process-Local Until Wave 5)
- Superseded by: None
- Related documents: ADR 0016, ADR 0022, ADR 0024, `development/10_IMPLEMENTATION_BLUEPRINT.md`, `development/engineering/standards/21_API_AND_DATABASE_STANDARDS.md`

## Context

ADR 0021 accepted process-local overlap locking for Phase 1 on the grounds that Wave 3 ran
executions from a single process, and deferred durable locking to Wave 5 where it could be
designed alongside the scheduler.

ADR 0022 removes that ground entirely. Under cron-backed activation **every activation is a
separate process**. Two cron activations of the same task share no memory, so
`ProcessLocalOverlapLock` does not merely provide a weaker guarantee than a durable lock —
it provides *no* overlap protection at all between scheduled activations. The moment cron
becomes the activation mechanism, the existing lock is inert for its primary purpose.

Separately, the realigned product introduces a durable work queue. A queue worker must claim
an item so two concurrently woken workers do not process it twice. Designed independently,
that would become a second concurrency system with its own claim semantics, its own recovery
rules, and its own bugs.

These are not two problems. Both ask the same question:

> Who owns the right to perform this piece of work, and for how long?

Scheduled overlap prevention, work-item claiming, abandoned-run recovery, worker leases, and
retry eligibility are all policies over one primitive. Building them separately guarantees
they will disagree — most damagingly about what happens when an owner dies mid-work, which
is the case that matters most and is tested least.

## Decision drivers

- Cron activation makes cross-process claiming a correctness requirement, not a future
  improvement.
- One primitive with two policies is far cheaper to reason about, test, and recover than two
  systems.
- Crash recovery semantics must be identical for a scheduled run and a queued item; an
  operator should not have to learn two models.
- A claim that cannot be verified must never be assumed.

## Considered options

### Option A — Keep the lock and the queue claim separate

Familiar shapes, each simple in isolation. Produces two expiry models, two recovery paths,
and two definitions of "abandoned". The divergence would surface during an incident.

### Option B — One durable claim primitive, two policies

A single `Claim` concept — subject, owner, lease expiry, fencing token — with scheduled-task
and work-item policies layered on top. More design effort once; one set of recovery
semantics thereafter.

### Option C — Rely on database row locking directly

Simple, but ties the semantics to a backend, gives no lease expiry across a crashed process,
and cannot express "this owner may still be alive but has not renewed".

## Decision

Adopt **Option B**.

### The primitive

TaskControl defines one durable claim capability:

> **A claim is durable, time-bounded ownership of a named subject by a named owner.**

Required properties:

| Property | Requirement |
|---|---|
| Durability | Survives the death of the claiming process. Held in the database, not in memory. |
| Subject | An opaque key. `task:<id>` for overlap; `work-item:<id>` for queue claims. |
| Owner | An explicit identity recorded with the claim, so a stale handle cannot release someone else's. |
| Lease expiry | Every claim expires. A dead owner must never block a subject forever. |
| Renewal | A live owner may extend its lease while working. |
| Fencing | A monotonic token, so a resumed owner whose lease already expired cannot act as though it still holds the claim. |
| Verifiability | If the claim store cannot be reached, acquisition **fails**. It is never assumed. |

### The two policies

**Scheduled overlap policy.** Before a cron-activated wrapper runs, it claims
`task:<task_id>`. A refused claim produces `ExecutionOutcome.BLOCKED` with
`blocked.overlap_lock_held` (ADR 0016). It never waits: a task that cannot start now is
recorded and explained, because blocking would leave the activation invisible while its
schedule moves on.

**Work-item claim policy.** A woken worker claims `work-item:<id>` before processing. A
refused claim means another worker has it, and the worker moves to the next eligible item.
Lease expiry is what makes a work item recoverable after a worker dies.

**Shared recovery.** An expired claim makes its subject eligible again. Whether the
interrupted work is retried, or recorded `UNKNOWN` pending reconciliation, is the existing
outcome and retry policy (ADR 0016) — not a second mechanism.

### The existing lock

`ProcessLocalOverlapLock` may remain **only** as a same-process test double and for
in-process unit tests. It must not be:

- used to protect a cron-activated execution;
- described as production overlap protection in any document, log line, API response, or UI
  surface;
- presented as merely "weaker" than the durable claim — between separate processes it
  provides nothing.

The `OverlapLock` port and its contract tests carry forward; the durable implementation must
pass them unchanged, plus the additional durability, expiry, and fencing tests.

### Sequencing

Cron-backed scheduled activation **may not be presented as overlap-safe until the durable
claim exists**. The blueprint must therefore deliver the durable claim in or before the wave
that delivers cron-backed activation, or that wave must state plainly that overlap
protection is not yet in force.

This is a blocking criterion, not a preference.

## Rationale

The cheapest moment to unify these is before either is built for its real purpose. The queue
does not exist yet, and the lock's current implementation is about to become inert. Building
one primitive now costs a design; building two costs a design, a second design, and the
incident where they disagree about a dead owner.

## Consequences

### Positive

- One set of ownership, expiry, and recovery semantics for the whole product.
- Cron-backed overlap protection becomes genuinely correct rather than nominally present.
- Worker crash recovery and scheduled-run recovery are the same mechanism.
- Fencing tokens make the resumed-owner case expressible rather than hoped away.

### Negative or accepted trade-offs

- More design work before the first cron slice can claim overlap safety.
- A claim requires a database round trip before every activation, which is a real cost on a
  host running many small jobs.
- Lease duration becomes a tuning parameter with a genuine failure mode at both extremes:
  too short and a live worker loses its claim, too long and a dead one blocks recovery.

### Risks and mitigations

- Risk: clock skew between processes corrupts expiry — mitigation: expiry is evaluated by
  the database's clock, not by the claimant's.
- Risk: the claim store becomes a bottleneck — mitigation: claims are per subject and short;
  measure before optimising.
- Risk: the process-local lock is used by accident — mitigation: its name, its docstring,
  and a test asserting no production path constructs it.

## Implementation constraints

- One module owns the claim primitive. Neither the scheduler adapter nor the queue defines
  its own.
- Claim acquisition failure due to an unreachable store is `CONDITION_ERROR` or
  `INFRASTRUCTURE_FAILED` — never an assumed acquisition.
- Every claim has an expiry. There is no unbounded claim.
- Release is idempotent and owner-checked.
- Contract tests run against every backend and include a genuine multi-**process** test.

## Validation

A reviewer can confirm: one claim module exists; no production path constructs
`ProcessLocalOverlapLock`; a multi-process test shows exactly one of two concurrently
activated processes proceeding; an expired lease makes a subject claimable again; and an
unreachable claim store produces a recorded failure rather than an execution.

## Migration and compatibility

No claims are persisted yet. `ProcessLocalOverlapLock` is retained as a test double; the
`OverlapLock` port is extended rather than replaced, so the runtime's orchestration is
unchanged.

## Future evolution and review triggers

Reconsider if a deployment needs claims across hosts that do not share a database, which
would require an external coordination service and a different primitive.

## Rejected alternatives

Option A was rejected because two concurrency systems will disagree about the crashed-owner
case, which is the one that matters. Option C was rejected because row locking offers no
lease expiry across a dead process and ties semantics to a backend.
