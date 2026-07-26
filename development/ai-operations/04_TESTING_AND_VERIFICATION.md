# Testing and Verification Playbook

- Document level: **3 — Specifications**
- Lifecycle state: Canonical

## Objective

Provide evidence that a change satisfies its acceptance criteria, preserves invariants, and fails safely.

## Test layers

### Domain tests

Verify invariants, value objects, state transitions, eligibility rules, outcome evaluation, retry decisions, and configuration resolution without frameworks or external services.

### Application tests

Verify use-case orchestration, transaction boundaries, port interactions, authorisation decisions, audit intent, and idempotency using fakes or controlled adapters.

### Adapter tests

Verify ORM mappings, migrations, API contracts, CLI behaviour, scheduler translation, executors, plugins, and external integrations.

### Integration tests

Verify meaningful boundaries such as application-to-database, API-to-application, deployment plan-to-adapter, and execution-to-outcome evaluation.

### End-to-end tests

Reserve these for critical user journeys. Keep them few, deterministic, and diagnosable.

## Required scenarios

Test more than the successful path. Consider:

- invalid input and invariant rejection;
- duplicate requests and idempotency;
- concurrency conflicts;
- timeout, cancellation, and retry exhaustion;
- partial external failure;
- permission denial;
- missing or conflicting configuration;
- migration upgrade and representative downgrade or recovery;
- redaction of secrets and sensitive output;
- audit and observability emission.

## Verification record

The agent must report:

- commands actually run;
- pass, fail, skip, and not-run status;
- environment limitations;
- pre-existing failures separated from introduced failures;
- manual checks performed;
- remaining unverified risks.

Never say a suite passed based only on code inspection. Never remove or weaken a failing test merely to make a change appear complete.

## Defect handling

When verification reveals a defect:

1. preserve or add a reproducing test;
2. identify the owning layer;
3. fix the narrowest correct cause;
4. rerun focused and relevant regression tests;
5. document any changed assumption or requirement.
