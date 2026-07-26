# Executions, Attempts, Results, and Expected Outcomes

## Purpose

The execution domain records what TaskControl tried to run, where it ran, how it behaved, and whether the intended operational outcome occurred.

The central rule is:

> Exit code zero is evidence of process completion, not proof of operational success.

## ExecutionRequest

An ExecutionRequest is a validated request to run one TaskRevision on one Target.

### Attributes

- `execution_request_id`.
- Task and revision identifiers.
- Trigger identifier and type.
- Target identifier.
- Requesting principal.
- Request time.
- Idempotency key.
- Parameter values or references.
- Resolved configuration digest.
- Approval reference, when required.
- Priority and queue metadata.

An ExecutionRequest should be rejected before creating an Execution when core identifiers are invalid. Eligibility denials should still produce a durable trigger decision.

## Execution

An Execution is the durable record for one requested run.

### Required attributes

- `execution_id`.
- Task, revision, and content digest.
- Trigger.
- Target.
- Environment.
- Requested, accepted, started, and completed timestamps as applicable.
- Current state.
- Final classification.
- Retry policy snapshot.
- Timeout snapshot.
- Resolved profile/calendar/condition version references.
- Correlation and causation identifiers.
- Requested cancellation metadata.
- Attempt references.
- Outcome evaluations.

### Execution states

- Requested.
- PendingApproval.
- Eligible.
- Queued.
- Starting.
- Running.
- Cancelling.
- Completed.
- Failed.
- TimedOut.
- Cancelled.
- Skipped.
- ConditionError.
- OutcomeFailed.
- InfrastructureFailed.

Implementations may use fewer internal states initially, but externally visible classification must preserve these meanings.

### Terminal classifications

- Succeeded: process and required outcomes succeeded.
- Failed: process started and returned a failing technical result.
- LaunchFailed: process could not be started.
- TimedOut: runtime exceeded timeout and termination policy completed.
- Cancelled: authorised cancellation prevented normal completion.
- Skipped: policy deliberately prevented execution.
- ConditionError: eligibility could not be determined.
- OutcomeFailed: process result was technically acceptable but one or more required outcomes failed.
- InfrastructureFailed: executor, agent, target, storage, or control-plane failure prevented reliable completion.
- Unknown: final state cannot be proven; requires reconciliation.

Never map all non-zero outcomes to a generic `failed` when the cause is known.

## ExecutionAttempt

An ExecutionAttempt is one runtime attempt within an Execution.

### Attributes

- `attempt_id` and sequence number.
- Execution identifier.
- Start and end timestamps.
- Executor adapter and version.
- Target observation metadata.
- Resolved runtime configuration reference.
- Process identifier or remote handle.
- ProcessResult.
- Log references.
- Heartbeat or liveness metadata.
- Retry decision.

### Attempt lifecycle

- Prepared.
- Launching.
- Running.
- Terminating.
- Finished.
- Lost.

A retry creates a new attempt. It does not overwrite the previous attempt result.

## ProcessResult

The technical result includes:

- Launch status.
- Exit code.
- Terminating signal.
- Timeout flag.
- Cancellation flag.
- Start and end times.
- Wall-clock duration.
- Standard output and error references.
- Output truncation metadata.
- Resource usage, when available.
- Executor error code and message.

### Output handling

- Capture output streams separately.
- Stream output when possible.
- Apply size limits.
- Mark truncation explicitly.
- Redact secrets before persistence or display.
- Preserve byte-safe artefacts when encoding is unknown.
- Do not rely on logs as the only execution state store.

## RetryPolicy

A retry policy defines:

- Maximum attempts.
- Retryable result classifications.
- Initial delay.
- Backoff strategy.
- Maximum delay.
- Jitter.
- Overall execution deadline.

Retries should normally apply only to transient classifications. Configuration validation, denied conditions, and deterministic outcome failures should not retry unless explicitly configured.

Each retry decision must record why the result was or was not retryable.

## Timeout and termination

A timeout policy defines:

- Runtime timeout.
- Graceful termination signal or mechanism.
- Grace period.
- Forced termination action.
- Child-process handling.

Timeout begins according to a documented point, preferably after successful process launch. Queue time and approval time should be tracked separately.

A timed-out process that cannot be confirmed terminated may produce Unknown or InfrastructureFailed rather than falsely claiming safe termination.

## Cancellation

Cancellation is a command with actor, reason, and timestamp.

Possible results:

- Cancelled before launch.
- Gracefully cancelled while running.
- Forcefully terminated.
- Cancellation rejected because already terminal.
- Cancellation uncertain because target communication was lost.

Cancellation does not delete history.

## ExpectedOutcome

An ExpectedOutcome is a declarative assertion evaluated after, during, or around execution.

### Attributes

- `expectation_id`.
- Name and description.
- Evaluator type and version.
- Required or advisory severity.
- Evaluation timing.
- Timeout.
- Configuration.
- Evidence retention policy.

### Initial evaluator types

- File exists.
- File absent.
- File modified after execution start.
- File age or freshness.
- File size range.
- Text or regular-expression match.
- HTTP status and response assertion.
- Exit code range.
- Runtime duration range.
- Structured JSON field assertion.

### Future evaluator types

- Database query assertion.
- Row count or data-quality assertion.
- Monitoring check state.
- Message publication.
- External system acknowledgement.
- Composite business outcome.

## OutcomeEvaluation

Each evaluation records:

- Execution and expectation identifiers.
- Evaluator version.
- Started and completed time.
- Status: passed, failed, error, skipped, inconclusive.
- Severity.
- Reason code and message.
- Redacted evidence.
- Evidence location and digest.

### Required versus advisory

- A failed required outcome changes final execution classification to OutcomeFailed.
- A failed advisory outcome produces warning state but may leave final classification SucceededWithWarnings if that classification is supported.

The UI must make required/advisory distinction visible.

## Result derivation

Final result is derived in a documented order:

1. Eligibility or approval terminal outcome.
2. Launch result.
3. Cancellation or timeout state.
4. Process technical result.
5. Retry exhaustion.
6. Required expected-outcome evaluations.
7. Advisory warnings.
8. Reconciliation confidence.

A pure function should derive the final classification from immutable evidence whenever practical.

## Provenance and reproducibility

Each Execution must be able to answer:

- Which TaskRevision content ran?
- Which profile versions were resolved?
- Which calendar and conditions were evaluated?
- Which target and observed platform state were used?
- Which executor version ran it?
- Which secret references, not values, were requested?
- Which deployment artefact or runtime package was used?

## Persistence guidance

Store Execution and ExecutionAttempt separately. Store large logs and evidence in an artefact store with durable references. Use append-oriented state transitions or an event history in addition to current-state columns.

State changes should use optimistic concurrency or transactional locking to prevent duplicate transitions.

## API guidance

Recommended resources:

- `POST /executions`.
- `GET /executions`.
- `GET /executions/{execution_id}`.
- `POST /executions/{execution_id}/cancel`.
- `POST /executions/{execution_id}/retry`.
- `POST /executions/{execution_id}/reconcile`.
- `GET /executions/{execution_id}/logs`.
- `GET /executions/{execution_id}/evidence`.

Manual run endpoints should create ExecutionRequests through the same application service used by scheduled triggers.

## CLI guidance

```text
taskctl run <task> --target local
taskctl execution list --task <task>
taskctl execution show <execution>
taskctl execution logs <execution> --follow
taskctl execution cancel <execution> --reason ...
taskctl execution retry <execution>
```

## UI guidance

Execution details should display:

- Overall classification.
- Timeline.
- Trigger reason.
- Revision and configuration provenance.
- Each attempt.
- Exit information.
- Logs with redaction and truncation indicators.
- Expected-outcome evaluations and evidence.
- Retry and cancellation decisions.
- Related audit events.

## Validation rules

- Every Execution references one immutable revision.
- Attempt sequence numbers are unique and ordered.
- Terminal states cannot return to running.
- Cancellation and retry commands are idempotent.
- Required expectations must be evaluated unless a stronger terminal result makes them inapplicable.
- Secret values must not be included in persisted runtime snapshots.
- A skipped trigger must not create a fake process attempt.
- Unknown target state must not be reported as success.

## Future extensions

- Remote-agent heartbeats.
- Distributed execution queues.
- Live log streaming.
- Execution leases.
- Workflow dependencies.
- Partial target fan-out.
- Automated incident creation.
- Replay with selected historical configuration.
- Statistical duration baselines and anomaly detection.