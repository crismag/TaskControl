# ADR 0021: Overlap Locking Is Process-Local Until Wave 5

- Document level: **1 — Architecture**
- Lifecycle state: Canonical
- Status: Accepted
- Date: 2026-07-27
- Owners: TaskControl maintainers
- Supersedes: None
- Superseded by: None
- Related documents: `development/engineering/standards/21_API_AND_DATABASE_STANDARDS.md`, `development/10_IMPLEMENTATION_BLUEPRINT.md`, ADR 0011, ADR 0016, ADR 0018

## Context

An overlap policy of `FORBID` promises that two executions of one task will not run
concurrently. Wave 3 must honour that promise, and the honest question is: across what?

The database standards are explicit: *"Never rely solely on in-process locks for
multi-process correctness."* A correct implementation needs a durable claim — a row with an
owner, a lease, an expiry, and a recovery rule for when the owner dies mid-run.

None of the machinery that makes such a claim safe exists yet. Ownership identity arrives
with the scheduler, stale-lock recovery needs the reconciliation that Wave 5 introduces, and
lease renewal is meaningless without a process whose liveness can be observed. Building a
durable lock in Wave 3 would mean inventing all of that in isolation, then rebuilding it
when the scheduler arrives with the real requirements.

Building it *badly* is the worse outcome: a lock that looks durable and is not is more
dangerous than an honest in-process lock, because operators will trust it.

## Decision drivers

- The promise a lock makes must match what it actually guarantees.
- Wave 3 runs executions from one process, so an in-process lock is sufficient *for what
  Wave 3 ships*.
- Durable locking, stale-lock recovery, ownership, and multi-process behaviour are one
  design problem and should be solved together.
- Replacing the implementation later must not require touching runtime orchestration.

## Considered options

### Option A — Build durable row-level locking now

Correct in the long run, but designed without the scheduler's requirements and without
anywhere to test multi-process contention. Likely rebuilt in Wave 5 anyway.

### Option B — No locking in Wave 3

Leaves `OverlapPolicy.FORBID` unimplemented, so a task that declares it gets no protection
and no error. Silently unhonoured configuration is exactly the failure mode this product
exists to remove.

### Option C — Process-local locking behind a port, explicitly named

Honour the policy within the boundary Wave 3 actually has, name the limitation in the type,
and make the implementation replaceable.

## Decision

Adopt **Option C**.

### The port

The runtime depends on an `OverlapLock` port, never on a concrete lock. Runtime
orchestration — acquire, run, release, classify contention — is written once and does not
change when the implementation does.

### The implementation

The Phase 1 implementation is named `ProcessLocalOverlapLock`. The name is the
documentation. It is described, in code and in prose, as preventing overlap **only within a
single TaskControl process**.

It must not be described as distributed, durable, multi-worker safe, or cluster-wide,
because it is none of those. Two TaskControl processes on one host, or the API and a
separate worker, will not see each other's locks.

### Contention behaviour

A task whose lock is held produces `ExecutionOutcome.BLOCKED` with reason code
`blocked.overlap_lock_held` (ADR 0016). Contention is a recorded, explained execution —
never a silent no-op and never a failure.

### Wave 5 requirement

Durable locking is a **requirement of Wave 5**, not an optional improvement. Wave 5 must
deliver:

1. A row-level claim durable across process restart.
2. An explicit owner identity for each claim.
3. A lease with an expiry, so a dead owner's claim does not block a task forever.
4. Stale-lock recovery that reconciles claims whose owner cannot be observed.
5. Multi-process contention tests, not merely multi-thread ones.
6. Documented behaviour when the lock store itself is unavailable — which must be
   `CONDITION_ERROR` or `INFRASTRUCTURE_FAILED`, never an assumed acquisition.

Until every one of those exists, TaskControl must not claim overlap protection beyond one
process, in documentation, in the UI, or in an API response.

## Rationale

An honest limited guarantee beats a dishonest broad one. Option C honours the configured
policy within the boundary that exists today, states that boundary in the type name so it
cannot be misread, and isolates the change behind a port so Wave 5 replaces an adapter
rather than reworking the runtime.

## Consequences

### Positive

- `OverlapPolicy.FORBID` is honoured for the deployment topology Phase 1 supports.
- The limitation is discoverable from the class name, not buried in a document.
- Wave 5 designs durable locking with the scheduler's real requirements in hand.

### Negative or accepted trade-offs

- Running two TaskControl processes against one database in Phase 1 does not give overlap
  protection. This must be stated in the deployment documentation, not discovered.
- A second implementation will be written in Wave 5. That is deliberate, not waste: the
  port and its contract tests carry forward.

### Risks and mitigations

- Risk: an operator assumes the lock is cluster-wide — mitigation: the class name, the port
  docstring, the deployment documentation, and this ADR all say otherwise.
- Risk: Wave 5 ships without durable locking — mitigation: it is listed as a Wave 5
  requirement in the blueprint, and this ADR states that the broader claim may not be made
  until it exists.

## Implementation constraints

- The runtime imports the port, never the implementation.
- The implementation's name contains `ProcessLocal`.
- No docstring, log line, API response, or document describes Phase 1 locking as durable,
  distributed, or multi-worker safe.
- Lock contention produces `BLOCKED` with `blocked.overlap_lock_held`.
- Lock acquisition and release are exercised by port contract tests that the Wave 5
  implementation must also pass.

## Validation

Contract tests assert acquisition, release, re-entrancy behaviour, and same-process
contention. A reviewer can confirm the runtime has no import of a concrete lock, and that
no document claims a guarantee wider than one process.

## Migration and compatibility

Wave 5 adds a durable implementation behind the same port. Runtime orchestration is
unchanged; composition selects the implementation.

## Future evolution and review triggers

Reconsider immediately if Phase 1 gains a second execution process before Wave 5, which
would make the in-process guarantee insufficient for a supported topology.

## Rejected alternatives

Option A was rejected as premature: the requirements that make a durable lock correct do not
exist yet. Option B was rejected because silently unhonoured configuration is the failure
mode the product exists to eliminate.
