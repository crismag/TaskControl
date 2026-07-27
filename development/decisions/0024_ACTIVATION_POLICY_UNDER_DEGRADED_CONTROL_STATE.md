# ADR 0024: Activation Policy When Control State Is Unreachable

- Document level: **1 — Architecture**
- Lifecycle state: Canonical
- Status: Accepted
- Date: 2026-07-27
- Owners: TaskControl maintainers
- Supersedes: None
- Superseded by: None
- Related documents: ADR 0008, ADR 0016, ADR 0022, ADR 0023, `development/product/PRODUCT_SCOPE.md`

## Context

ADR 0022 makes cron the activation mechanism. That creates a case the internal-scheduler
design never had to face:

> Cron wakes a managed task. The wrapper starts. TaskControl's database is unreachable.

Under an internal scheduler this could not happen — a scheduler that could not reach its
database was not scheduling. Under cron, activation has already occurred and something must
decide what to do next, in a short-lived process, with no control plane to ask.

The decision is genuinely contested, and the honest answer is that it depends on the task:

- A **nightly backup** that does not run is a serious operational failure. Losing the record
  that it ran is an inconvenience. Here, running blind is better than not running.
- A **settlement reconciliation** that runs without a durable attempt record may be
  impossible to audit and may be re-run later by an operator who cannot tell whether it
  already happened. Here, not running is better than running unrecorded.

Both are correct for their task. A single global answer would be wrong for half the estate,
and — worse — leaving it unspecified means the behaviour becomes whatever the first
implementation happens to do, discovered during an incident.

## Decision drivers

- The behaviour must be deliberate and visible in the task definition, never accidental.
- Auditability and availability genuinely conflict here; the product must not pretend
  otherwise.
- A short-lived wrapper cannot wait for a control plane to return.
- Whatever runs unrecorded must become recorded eventually, or the audit trail is a lie.

## Considered options

### Option A — Always fail closed

Never execute without a durable attempt record. Perfectly auditable; turns a database outage
into an estate-wide outage of every scheduled job, including the ones whose whole purpose is
to keep running.

### Option B — Always execute

Maximum availability; produces silent unrecorded runs, which for a side-effecting job is
exactly the ambiguity the product exists to eliminate.

### Option C — Per-task policy, explicit in the definition

Neither default is imposed. The task states which failure it prefers.

## Decision

Adopt **Option C**. Every task carries an activation policy:

```yaml
activation_policy: require_control_state     # managed-strict
```

```yaml
activation_policy: continue_with_local_journal   # availability-first
```

### `require_control_state` — managed-strict

```text
Cannot create a durable attempt record
        -> do not execute the runnable
        -> write what can be written locally
        -> exit with an infrastructure failure status
```

The runnable does not run. Once persistence returns, the activation is reconciled as
`INFRASTRUCTURE_FAILED` with reason `infrastructure_failed.storage_failed` (ADR 0016) — a
recorded non-run, not silence.

For work where an unrecorded run is worse than a missed one: financial processing,
regulated operations, anything a human may re-run by hand.

### `continue_with_local_journal` — availability-first

```text
Persistence unavailable
        -> execute the installed runnable
        -> write a local journal entry: identifiers, times, result, exit status, output refs
        -> exit with the runnable's own status
        -> reconcile the journal into central history when persistence returns
```

The work happens. The record catches up.

For work where missing the run is worse than temporarily missing central observability:
backups, log rotation, cleanup, cache warming.

### The journal is not optional

`continue_with_local_journal` without a journal is simply an unrecorded run. The journal
must capture enough to reconstruct the attempt — task and revision identifiers, activation
time, start and end, exit status, termination cause, and references to captured output — and
must be written before the process exits.

Reconciliation is a first-class operation, not a manual clean-up: a later TaskControl
invocation ingests journal entries into central history, marks them reconciled, and flags
any it cannot match.

### The default

The first release defaults to **`require_control_state`**.

An operator who has not thought about this case gets the auditable behaviour, and the
failure is loud rather than silent. Choosing availability over auditability should be a
deliberate act recorded in the task definition, not something inherited by omission.

### Interaction with claims

Both policies still require a claim (ADR 0023) before executing. A claim store that cannot
be reached is not permission to run:

- under `require_control_state`, an unreachable claim store means do not execute;
- under `continue_with_local_journal`, an unreachable claim store means overlap protection
  is not in force, which must be journalled explicitly so reconciliation can flag a possible
  concurrent run.

Availability-first never means "assume the claim succeeded". It means "record honestly that
we proceeded without one".

## Rationale

The conflict between auditability and availability is real and task-specific, so the product
models it rather than resolving it globally. Making it a per-task field forces the decision
to be made once, visibly, by whoever knows what the task does — and puts it in the
definition where a reviewer can see it.

## Consequences

### Positive

- Behaviour during a partial outage is designed rather than discovered.
- Backups keep running; regulated work stays auditable.
- A reviewer can see a task's degraded-mode behaviour in its definition.
- Silent unrecorded execution is impossible: either it does not run, or it is journalled.

### Negative or accepted trade-offs

- A local journal is a second, weaker record store with its own format, rotation, and
  permissions concerns.
- Reconciliation is real work with real edge cases: duplicates, journals from a rebuilt host,
  entries whose task no longer exists.
- Two policies mean two paths to test and two operator mental models.

### Risks and mitigations

- Risk: journals accumulate unreconciled and unnoticed — mitigation: unreconciled journal
  entries are a health signal surfaced through readiness and the API, not just a directory
  on disk.
- Risk: `continue_with_local_journal` is chosen by default for convenience — mitigation: the
  default is strict, and choosing otherwise is a visible field in the definition.
- Risk: a journal entry contains sensitive output — mitigation: journals obey the same
  redaction rules as central logs; the secret rules do not weaken because persistence is
  down.

## Implementation constraints

- The policy is part of the task revision and therefore immutable once published.
- A wrapper must decide from locally deployed assets alone; it may not require the control
  plane to learn its own policy.
- Journal entries are append-only and redacted to the same standard as central records.
- Reconciliation is idempotent: ingesting one entry twice produces one execution record.
- A journalled run reaches a terminal state in central history once reconciled, in keeping
  with the terminal-state guarantee.

## Validation

A reviewer can confirm: a task with each policy behaves as described with persistence
stopped; a strict-mode activation produces a recorded `INFRASTRUCTURE_FAILED` once
persistence returns; a journalled run reconciles into exactly one execution record; and
re-running reconciliation changes nothing.

## Migration and compatibility

No tasks exist. The field is added to the revision schema with `require_control_state` as
the default, so an existing definition that omits it gets the auditable behaviour.

## Future evolution and review triggers

Reconsider if a third mode proves necessary — for example, "execute only if the last
successful run was more than N hours ago", which trades a different pair of risks — or if
journal reconciliation proves too error-prone to be trusted for regulated work.

## Rejected alternatives

Option A was rejected because it turns a database outage into an outage of every scheduled
job, including those whose purpose is to keep running regardless. Option B was rejected
because a silent unrecorded run of a side-effecting job is precisely the ambiguity
TaskControl exists to remove.
