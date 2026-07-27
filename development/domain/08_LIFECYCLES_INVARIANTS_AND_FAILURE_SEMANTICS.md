# Lifecycles, Invariants, and Failure Semantics

- Document level: **1 — Architecture**
- Lifecycle state: Canonical

## Purpose

This document defines system-wide rules that cross individual domain specifications. These rules should become domain tests, database constraints where appropriate, and application-service guards.

## Global invariants

1. Every operational action references stable identifiers.
2. Every execution references one immutable TaskRevision.
3. Every deployment references one immutable DeploymentPlan.
4. Published definitions never mutate in place.
5. Secrets are represented by references outside the materialisation boundary.
6. Scheduled due time, actual trigger time, execution start, and completion remain distinct.
7. A skipped occurrence never creates a fake process attempt.
8. Process success and expected-outcome success remain distinct.
9. Target configured state and observed state remain distinct.
10. High-risk state changes are authorised and audited.
11. External side effects are idempotent or protected by explicit deduplication.
12. Unknown state is represented honestly rather than guessed as success or failure.

> **Vocabulary note.** The transition diagrams below name states illustratively. The normative
> `ExecutionState` and `ExecutionOutcome` members, and their serialisation, are fixed by **ADR 0016**;
> where a name here differs, ADR 0016 governs.
13. Configuration resolution is deterministic and explainable.
14. Adapter-specific concepts do not redefine the domain.
15. Historical records remain interpretable after definitions change.

## Task lifecycle transitions

Allowed baseline transitions:

```text
Draft -> Active
Draft -> Archived
Active -> Suspended
Suspended -> Active
Active -> Retired
Suspended -> Retired
Retired -> Active     only by explicit restoration policy
Retired -> Archived
```

Invalid examples:

- Archived directly to Active without restoration.
- Active without a published revision.
- Physical deletion after execution history exists.

## Revision lifecycle transitions

```text
Draft -> Published
Published -> Superseded
Published -> Withdrawn
Superseded -> Active selection through rollback, without mutating content
Draft -> Discarded
```

A published revision remains published even after it stops being active.

## Trigger lifecycle

```text
Received -> Validating -> Evaluating
Evaluating -> Eligible
Evaluating -> Skipped
Evaluating -> PendingApproval
Evaluating -> ConditionError
Eligible -> ExecutionCreated
PendingApproval -> Eligible | Rejected | Expired
```

Duplicate trigger processing should return the existing result or no-op safely.

## Execution lifecycle

A simplified valid path:

```text
Requested -> Eligible -> Queued -> Starting -> Running -> Completed
```

Alternative terminal paths:

- Requested -> Skipped.
- Requested -> PendingApproval -> Cancelled/Expired.
- Starting -> LaunchFailed.
- Running -> TimedOut.
- Running -> Cancelling -> Cancelled.
- Running -> Failed.
- Running -> OutcomeFailed after process completion and evaluation.
- Any active state -> Unknown when reliable control is lost.

Terminal execution state is immutable except through a reconciliation record that explains and audits the correction. Do not rewrite history silently.

## Deployment lifecycle

```text
PlanCreated -> PendingApproval -> Applying -> Applied
PlanCreated -> Applying -> Failed
Applying -> PartiallyApplied
Failed/PartiallyApplied -> RollingBack -> RolledBack | RollbackFailed
```

A stale plan cannot be applied without regeneration or explicit high-risk override.

## Approval lifecycle

```text
Pending -> Approved | Rejected | Expired | Cancelled | Superseded
```

Approval applies only to the exact immutable digest requested.

## Failure taxonomy

### Validation failures

The requested definition is invalid before side effects begin.

Examples:

- Invalid cron expression.
- Missing required profile key.
- Unsupported executor.
- Invalid target selector.

These are not execution failures.

### Eligibility denials

The system intentionally decides not to execute.

Examples:

- Holiday.
- Maintenance window.
- Runtime switch disabled.
- Overlap forbidden.

These produce skipped or denied outcomes.

### Eligibility errors

The system cannot determine whether execution is allowed.

Examples:

- Calendar source unavailable beyond allowed staleness.
- Condition evaluator times out.
- Target state cannot be inspected.

Default production behaviour should fail closed.

### Launch failures

The executor cannot start the process.

Examples:

- Executable not found.
- Working directory missing.
- Permission denied.
- Secret materialisation failed.

No running attempt should be claimed.

### Process failures

The process starts and returns a failing exit code or signal.

### Timeout failures

The process exceeds the runtime limit. The system must separately record whether termination was confirmed.

### Cancellation outcomes

An authorised cancellation interrupts or prevents normal completion.

### Outcome failures

The process completes technically, but required expected outcomes fail.

### Infrastructure failures

TaskControl cannot reliably coordinate or observe the operation.

Examples:

- Database unavailable during state transition.
- Agent disconnected.
- Artefact store failure.
- Scheduler apply result unknown.

### Integration failures

External adapters fail with classified transient or permanent errors.

### Unknown outcomes

Evidence is insufficient to claim a final result. Unknown is a valid and important classification requiring reconciliation.

## Error representation

Domain and application errors should include:

- Stable error code.
- Category.
- Human-readable message.
- Retryable flag.
- Resource identifiers.
- Correlation identifier.
- Redacted details.
- Suggested operator action when known.

Do not expose raw stack traces through ordinary APIs.

## Idempotency rules

Operations requiring idempotency:

- Scheduled trigger creation.
- Manual/API execution request with client key.
- Deployment application per plan and target.
- Cancellation request.
- Notification delivery.
- Webhook delivery.
- Agent result reporting.

Idempotency records should include request digest and result reference. Reusing a key with different content must fail.

## Concurrency rules

- TaskRevision publication uses optimistic concurrency.
- Active-revision changes are atomic.
- Execution state transitions reject stale versions.
- Concurrency limit evaluation and execution reservation must be atomic enough to prevent overlap races.
- Deployment apply locks or leases target managed state.
- Profile publication prevents duplicate version numbers.

## Transaction boundaries

A database transaction should normally include:

- Domain state change.
- Corresponding audit event.
- Outbox event for asynchronous follow-up.

External side effects should not occur inside a long database transaction. Use plan records, outbox patterns, leases, and reconciliation.

## Time semantics

- Store timestamps in UTC.
- Preserve originating time zone and nominal local schedule time.
- Use monotonic clocks for local duration measurement.
- Do not compare naive datetimes.
- Record clock source uncertainty for remote agents when relevant.

## Deletion semantics

Prefer lifecycle states and retention policies over physical deletion.

Physical deletion may be allowed only for unreferenced drafts or ephemeral artefacts under policy. Deletion must not break historical provenance.

## Version semantics

Version independently:

- Public configuration schemas.
- TaskRevision content.
- Profile content.
- Calendar content.
- Adapter contracts.
- Plugin manifests.
- API versions.
- Generated artefact formats.
- Agent protocol.

Do not use one application version as a substitute for all contract versions.

## Security invariants

- Commands are executed without implicit shell interpolation by default.
- Path access is constrained by target/executor policy.
- API, CLI, scheduler, and UI all call the same authorisation-aware application services.
- Secrets are redacted from logs, errors, API output, audit, and artefact previews.
- Plugin and adapter capabilities are least privilege.
- Dangerous overrides are explicit and auditable.

## Observability invariants

Every significant operation has:

- Correlation identifier.
- Structured state transitions.
- Actor or system identity.
- Resource identifiers.
- Start/end timestamps.
- Classified result.
- Human-readable explanation.

## Testing implications

Create tests for:

- Every allowed and denied lifecycle transition.
- Revision immutability.
- Trigger idempotency.
- Configuration precedence and trace.
- Secret redaction.
- Skip versus failure classification.
- Process success with outcome failure.
- Timeout with confirmed and unconfirmed termination.
- Partial deployment.
- Stale-plan rejection.
- Approval digest mismatch.
- Drift classification.
- Retry classification.
- Concurrent overlap prevention.

Property-based tests are especially useful for schedule preview, precedence resolution, state machines, and idempotency.
