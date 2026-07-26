# Testing and Quality Strategy

## Principle

Tests prove behaviour, contracts, and recovery properties. Coverage percentage alone does not prove quality.

## Test layers

### Domain tests

Fast, deterministic tests for invariants, state transitions, policies, result classification, configuration precedence, eligibility, retries, approvals, and drift decisions. Domain tests must not require frameworks, networks, or databases.

### Application tests

Verify use-case orchestration, permission enforcement, repository interactions, transaction boundaries, auditing, idempotency, and event publication using fakes or controlled adapters.

### Adapter and repository tests

Verify mapping, queries, migrations, vendor error translation, integration contracts, redaction, and recovery behaviour against realistic dependencies.

### API and CLI tests

Verify authentication, validation, status/error mapping, idempotency, pagination, output contracts, and that transports delegate rather than duplicate business behaviour.

### UI tests

Verify critical user journeys, accessibility, loading and error states, permission-aware presentation, and safe handling of stale or conflicting updates.

### End-to-end tests

Cover a small set of critical workflows such as task creation, scheduling eligibility, execution and outcome evaluation, deployment plan/apply/verify, authorisation denial, and audit retrieval.

## Required properties

- Deterministic clocks and identifiers where relevant.
- No dependence on test order.
- No live external services in the default unit suite.
- Every defect fix adds a regression test when feasible.
- Failure paths receive first-class tests.
- Retry, timeout, cancellation, duplicate delivery, crash recovery, and partial-side-effect cases are tested.
- Schema migrations are tested from supported prior states.

## Coverage guidance

Coverage thresholds may be configured later, but critical domain and application decisions require direct behavioural tests. Excluding difficult code from coverage does not remove the testing obligation.

## Test data

Use factories/builders that express domain intent. Never include real credentials or production data. Fixtures should remain minimal and local to the behaviour under test.

## Quality gates

Before merge:

1. formatting and static analysis pass;
2. type checking passes for governed modules;
3. unit and integration suites pass;
4. migrations are validated where applicable;
5. security-sensitive changes receive targeted review;
6. documentation and examples are current;
7. no unresolved high-severity regression is knowingly introduced.
