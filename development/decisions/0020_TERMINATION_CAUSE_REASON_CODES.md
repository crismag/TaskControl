# ADR 0020: Reason Codes Distinguish Termination Causes

- Document level: **1 — Architecture**
- Lifecycle state: Canonical
- Status: Accepted
- Date: 2026-07-27
- Owners: TaskControl maintainers
- Supersedes: the reason-code namespace restriction in ADR 0016; that ADR otherwise stands
- Superseded by: None
- Related documents: ADR 0008, ADR 0016, `development/domain/04_EXECUTIONS_ATTEMPTS_RESULTS_AND_EXPECTATIONS.md`

## Context

ADR 0016 requires a reason code for four outcomes — `SKIPPED`, `BLOCKED`,
`CONDITION_ERROR`, and `INFRASTRUCTURE_FAILED` — and restricts reason-code namespaces to
exactly those four. Every other outcome carries no reason code.

Wave 3 shows that rule is too narrow. Three different events produce a killed process, and
at the operating-system level they are indistinguishable: the runtime enforcing a timeout,
an operator cancelling the execution, and something outside TaskControl sending a signal —
an OOM killer, a deployment script, an impatient administrator.

The outcome alone cannot separate them:

* A timeout and a cancellation both end a running process deliberately, but one is a
  failure of the work and the other is an authorised human decision. `TIMED_OUT` and
  `CANCELLED` do distinguish those two.
* An externally killed process currently classifies as `FAILED` with the signal recorded
  only in a free-text explanation. An operator asking "did something kill my job, or did it
  crash?" has to read prose, and a dashboard cannot count it.

Journey 13 requires the interface to answer "what happened" from stored fields. A cause
that exists only in an explanation string is not a stored field.

## Decision drivers

- Termination cause must be machine-readable, not merely explained in prose.
- The mechanism that ends a process is the same in all three cases; the *reason* is not.
- Outcome membership must stay stable — adding outcomes is breaking for exhaustive clients.
- Reason codes are already an open, additive, namespaced vocabulary. Extending their reach
  costs nothing at the schema level.

## Considered options

### Option A — Add outcomes for each cause

`EXTERNALLY_TERMINATED`, `CANCELLED_BY_USER`, and so on. Breaks every exhaustive client,
inflates the enum that ADR 0016 deliberately kept small, and confuses two different
questions: *how did this end* and *why*.

### Option B — Record the cause in the explanation only

No schema change. Leaves the cause unqueryable, uncountable, and unfilterable. Fails
Journey 13.

### Option C — Permit reason codes on termination-bearing outcomes

Keep the outcome enum exactly as ADR 0016 fixed it. Widen the reason-code vocabulary so
`FAILED`, `TIMED_OUT`, and `CANCELLED` may — and where the cause is knowable, must — carry
one.

## Decision

Adopt **Option C**.

### Namespaces

Reason codes may now be namespaced under seven outcomes rather than four:

| Outcome | Reason code | Required? |
|---|---|---|
| `SKIPPED` | `skipped.*` | required |
| `BLOCKED` | `blocked.*` | required |
| `CONDITION_ERROR` | `condition_error.*` | required |
| `INFRASTRUCTURE_FAILED` | `infrastructure_failed.*` | required |
| `TIMED_OUT` | `timed_out.*` | required |
| `CANCELLED` | `cancelled.*` | required |
| `FAILED` | `failed.*` | optional |

`FAILED` is optional because a process that simply exits non-zero has no cause beyond its
exit status. When a `FAILED` result *does* have a knowable cause — an external signal — a
reason code is expected.

`SUCCEEDED`, `LAUNCH_FAILED`, `OUTCOME_FAILED`, and `UNKNOWN` carry no reason code.
`LAUNCH_FAILED` and `OUTCOME_FAILED` already explain themselves through the launch error
and the expectation results respectively.

### Initial termination reason codes

```text
timed_out.run_timeout_exceeded      The runtime enforced the configured timeout.
cancelled.requested_by_user         An authorised cancellation was requested.
cancelled.superseded                A replace-overlap policy cancelled this run.
failed.terminated_externally        A signal arrived that TaskControl did not send.
```

### Termination cause is tracked, not inferred

The runtime records **why** it terminated a process at the moment it does so, rather than
guessing afterwards from the signal number. A `SIGKILL` looks identical whether TaskControl
sent it or the kernel did; only the runtime knows which.

This is modelled as a `TerminationCause` on the process result, and classification reads
it. Inferring cause from signal number would be a guess, and ADR 0008 forbids guessing.

## Rationale

Option C answers the operator's question with a stored, countable field while leaving the
outcome enum — the thing clients switch on — untouched. It uses a vocabulary that was
already designed to be open and additive, which is why extending it is not a breaking
change.

## Consequences

### Positive

- "Was my job killed, or did it crash?" is answerable from a stored field.
- Timeout, cancellation, and external termination are separable in queries and metrics.
- No new outcome members; exhaustive clients are unaffected.

### Negative or accepted trade-offs

- Seven reason-code namespaces instead of four is more vocabulary to learn.
- The runtime must thread a termination cause through to the process result, which is one
  more thing a future executor adapter must get right.

### Risks and mitigations

- Risk: an adapter reports `EXTERNAL` for a termination TaskControl actually requested —
  mitigation: the cause is set by the runtime at the point of the request, not by the
  adapter observing the aftermath.
- Risk: reason-code sprawl across seven namespaces — mitigation: codes stay registered in
  one module and namespaced by outcome, as ADR 0016 requires.

## Implementation constraints

- A `TIMED_OUT` or `CANCELLED` outcome without a reason code is invalid and must be
  rejected at construction.
- Termination cause is recorded when termination is *requested*, never inferred from the
  resulting signal.
- Adding a reason code remains a non-breaking change; clients must tolerate unknown codes.

## Validation

Parameterised tests assert the required/optional table above, that each termination cause
produces its expected outcome and reason code, and that an externally killed process is
distinguishable from a timeout in stored fields alone.

## Migration and compatibility

No stored data exists with these outcomes yet. Reason code remains a nullable column
alongside outcome, so no schema change is required.

## Future evolution and review triggers

Reconsider if OOM-kill detection becomes possible, which would justify splitting
`failed.terminated_externally` into a resource-exhaustion code, or if remote workers
(Phase 3) introduce terminations whose cause the control plane cannot observe.

## Rejected alternatives

Option A was rejected because it breaks exhaustive clients to express something the reason
code already models. Option B was rejected because a cause held only in prose cannot be
queried, counted, or filtered.
