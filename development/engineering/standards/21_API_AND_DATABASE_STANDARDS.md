# API and Database Standards

- Document level: **1 — Architecture**
- Lifecycle state: Canonical

## API responsibilities

The API is a transport adapter. Endpoints authenticate, validate transport input, call application services, and map results to stable response contracts.

Endpoints must not contain business decisions, direct ORM queries, deployment logic, retry policy, or scheduler-specific behaviour.

## REST contracts

- Use resource-oriented, predictable URLs.
- Distinguish commands from resource replacement when an operation has domain meaning.
- Use idempotency keys for retried write operations where duplicate side effects are possible.
- Use consistent pagination, filtering, sorting, and timestamp formats.
- Return machine-readable error codes plus safe human-readable messages.
- Do not expose stack traces, secrets, internal paths, or vendor errors.
- Version breaking contracts deliberately.

## Validation

Transport validation checks shape and syntax. Domain validation checks meaning and invariants. Passing a Pydantic schema does not prove a command is valid.

## Persistence boundary

SQLAlchemy models represent storage, not the domain. Repositories translate between persistence records and domain objects. ORM sessions must not escape infrastructure or repository boundaries.

## Transactions

Application use cases define transaction boundaries. A transaction should cover the smallest complete consistency unit. External side effects must not be assumed atomic with database commits; use durable state, outbox patterns, idempotency, or reconciliation where needed.

## Migrations

- Every schema change uses Alembic.
- Migrations are reviewable, ordered, and tested from supported upgrade paths.
- Destructive changes require staged migration and recovery planning.
- Data migrations must be restartable or explicitly guarded.
- Downgrade limitations must be documented.

## Data integrity

Use database constraints for invariants that the database can reliably enforce, while retaining domain validation for meaningful errors and non-persistence flows.

## Indexes

Indexes require a documented query or integrity need. Review write cost, storage cost, selectivity, and expected access patterns. Avoid speculative indexing.

## Concurrency

Use optimistic concurrency for user-edited versioned resources where practical. Define lock ownership and expiry explicitly for operational execution. Never rely solely on in-process locks for multi-process correctness.

## Deletion and audit

Choose archive, soft-delete, retention, or hard-delete behaviour per domain policy. Audit records and immutable historical revisions must not be silently rewritten or cascaded away.
