# Testing and Quality Strategy

- Document level: **1 — Architecture**
- Lifecycle state: Canonical
- Supersedes: testing section of `archive/06_ENGINEERING_STANDARDS.md`

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

### Contract tests

Shared test suites that every implementation of a port must pass — executor, scheduler, deployment, secret, notification, and repository. A new adapter is not complete until it passes the contract suite for its port unmodified.

### Golden-file tests

Deterministic generated output — resolved configuration snapshots, validation reports, exported schemas, and from Phase 2 every generated scheduler artefact — is compared against a committed golden file. A diff is a deliberate decision, reviewed like code, never an incidental change.

### Property and parameterised tests

Schedules, calendars, and configuration precedence are tested across generated inputs rather than hand-picked examples. Required coverage includes DST spring-forward and fall-back in multiple time zones, holiday and exceptional-closure boundaries, leap days, and the full configuration layer precedence matrix.

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
