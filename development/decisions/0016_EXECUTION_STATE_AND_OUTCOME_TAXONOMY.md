# ADR 0016: Execution State and Outcome Taxonomy

- Document level: **1 — Architecture**
- Lifecycle state: Canonical
- Status: Accepted
- Date: 2026-07-26
- Owners: TaskControl maintainers
- Supersedes: Outcome lists in `development/archive/03_DOMAIN_MODEL.md` and `development/archive/01_FULL_APPLICATION_GENERATION_PROMPT.md`
- Superseded by: None
- Related documents: `development/domain/04_EXECUTIONS_ATTEMPTS_RESULTS_AND_EXPECTATIONS.md`, `development/domain/08_LIFECYCLES_INVARIANTS_AND_FAILURE_SEMANTICS.md`, ADR 0008

## Context

The distinction between skip, block, process failure, outcome failure, timeout, cancellation, and infrastructure failure is TaskControl's central product claim. Three documents defined it three incompatible ways:

| Source | Vocabulary |
| --- | --- |
| `03_DOMAIN_MODEL.md` | `SUCCEEDED FAILED SKIPPED BLOCKED TIMED_OUT CANCELLED SUPPRESSED UNKNOWN` |
| `domain/04` | `Succeeded Failed LaunchFailed TimedOut Cancelled Skipped ConditionError OutcomeFailed InfrastructureFailed Unknown` |
| `prompts/01` | `pending evaluating skipped blocked running succeeded failed outcome_failed timed_out cancelled lost` |

The three disagree on casing, on membership, and — more seriously — on whether lifecycle states and terminal classifications are one vocabulary or two. `prompts/01` mixes `running` and `pending` (lifecycle) with `succeeded` and `timed_out` (classification) in a single list, which forces an implementation to represent "was running, then timed out" as a lossy single field.

## Decision drivers

- A running execution and a finished execution answer different questions; one enum cannot serve both.
- Retry eligibility must be derivable from the classification alone.
- Skip and block are operationally different and must not collapse.
- Honest representation of unproven state is required (ADR 0008).
- One wire format so API, CLI, UI, logs, and metrics agree.

## Considered options

### Option A — One flat status enum

Simple storage, single column. Loses the ability to record how a finished execution reached its end while it is still in flight, and forces artificial members such as `running` to sit beside `timed_out`.

### Option B — Two enums: lifecycle state plus terminal outcome

Slightly more storage and more code. Preserves the in-flight/terminal distinction, makes illegal transitions checkable, and lets outcome be `NULL` until an execution finishes.

## Decision

Adopt **Option B**. TaskControl defines two enumerations and one open reason-code vocabulary.

### `ExecutionState` — lifecycle

| Member | Meaning |
| --- | --- |
| `PENDING` | Execution record created; not yet evaluated. |
| `EVALUATING` | Run conditions and dependencies are being evaluated. |
| `RUNNING` | At least one attempt is in flight. |
| `CANCELLING` | Cancellation requested; termination in progress. |
| `FINISHED` | Terminal. `outcome` is set and immutable. |

`outcome` is `NULL` for every state except `FINISHED`, where it is required.

### `ExecutionOutcome` — terminal classification

| Member | Meaning | Retryable |
| --- | --- | --- |
| `SUCCEEDED` | Process succeeded and every required expectation passed. | no |
| `FAILED` | Process started and returned a failing technical result. | yes |
| `LAUNCH_FAILED` | Process could not be started (missing binary, bad working directory, permission denied). | yes |
| `OUTCOME_FAILED` | Process result was technically acceptable but a required expectation failed. | policy |
| `TIMED_OUT` | Runtime exceeded its timeout and the termination policy completed. | policy |
| `CANCELLED` | An authorised cancellation prevented normal completion. | no |
| `SKIPPED` | Policy deliberately declined to run: the task was not applicable now. | no |
| `BLOCKED` | The task was applicable but a guard prevented starting: lock held, dependency unmet, manual hold, approval pending. | no |
| `CONDITION_ERROR` | Eligibility could not be determined; the guard itself failed. | yes |
| `INFRASTRUCTURE_FAILED` | Executor, target, storage, or control-plane failure prevented reliable completion. | yes |
| `UNKNOWN` | Final state cannot be proven and requires reconciliation. | no |

`SKIPPED` versus `BLOCKED` is the distinction between "should not run" and "should run but may not start yet". A holiday calendar produces `SKIPPED`; a held overlap lock produces `BLOCKED`. Retrying a `SKIPPED` execution is always wrong; retrying a `BLOCKED` one is a scheduling question, not a runtime one.

`retryable` above describes eligibility, not obligation. `policy` means the retry policy decides; `OUTCOME_FAILED` and `TIMED_OUT` are only retried when the task opts in, because both can be side-effecting.

### Removed members

- `SUPPRESSED` is not an execution outcome. Suppression is a notification-delivery decision and belongs to `NotificationDelivery`. An execution that ran and succeeded while its alert was suppressed is `SUCCEEDED`.
- `lost` is replaced by `UNKNOWN` (state unproven) or `INFRASTRUCTURE_FAILED` (loss attributable to a component).

### Reason codes

Outcome answers *what*; reason code answers *why*. Reason codes are an open, namespaced, machine-readable vocabulary stored beside the outcome, never encoded into it. Initial codes:

```text
skipped.calendar_closed          blocked.overlap_lock_held
skipped.switch_disabled          blocked.dependency_not_satisfied
skipped.environment_not_allowed  blocked.manual_hold
skipped.window_closed            blocked.approval_pending
condition_error.evaluator_failed infrastructure_failed.executor_unavailable
```

Every `SKIPPED`, `BLOCKED`, `CONDITION_ERROR`, and `INFRASTRUCTURE_FAILED` outcome requires a reason code. Codes are additive; adding one is not a breaking change, and clients must tolerate unknown codes.

### Serialisation

Python enum members are `SCREAMING_SNAKE_CASE`; their values and every external representation — API JSON, CLI output, log fields, metric labels, export formats — are `lower_snake_case`. `ExecutionOutcome.TIMED_OUT.value == "timed_out"`. No other casing appears on any wire.

## Rationale

Two enums cost one nullable column and remove a class of ambiguity that would otherwise reach the API, the UI, and every integration. The membership is `domain/04`'s, which is the most operationally honest of the three, plus `BLOCKED` restored from `03_DOMAIN_MODEL.md` because guard-prevented starts are a real and distinct condition that the product exists to surface.

## Consequences

### Positive

- Illegal transitions are checkable in the domain.
- Retry logic reads directly from the classification table.
- Failure investigation (`USER_JOURNEYS.md`, Journey 13) is answerable from stored fields.

### Negative or accepted trade-offs

- Two columns and two enums instead of one.
- Consumers must handle `outcome == null` for in-flight executions.

### Risks and mitigations

- Risk: implementations default unclassifiable results to `FAILED` — mitigation: classification is a tested pure function; `UNKNOWN` is a legitimate answer.
- Risk: reason-code sprawl — mitigation: codes are namespaced by outcome and registered in one module.

## Implementation constraints

- Both enums live in `src/taskcontrol/domain/execution/`. No other module may define an execution status vocabulary.
- Never map a non-zero exit to a generic failure when the cause is known.
- An execution that is skipped or blocked is still a recorded execution with zero attempts.
- Attempts carry their own process result; the execution-level outcome is derived from attempts plus expectation evidence.

## Validation

Parameterised tests cover every member, every legal and illegal transition, the retry-eligibility table, and the requirement that reason codes accompany the four outcomes that mandate them. A test asserts every enum value is `lower_snake_case`.

## Migration and compatibility

No code or data exists. Once the API is published, adding an outcome member is breaking for exhaustive clients and requires a version note; adding a reason code is not.

## Future evolution and review triggers

Reconsider if distributed workers (Phase 3) introduce states that `UNKNOWN` cannot honestly express, or if expectation evaluation becomes asynchronous from execution completion.

## Rejected alternatives

Option A was rejected because it cannot represent an in-flight execution and its eventual classification without either a lossy field or an implicit convention.
