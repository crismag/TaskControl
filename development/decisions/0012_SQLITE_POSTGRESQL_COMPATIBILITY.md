# ADR 0012: SQLite First with PostgreSQL Compatibility

- Status: Accepted
- Date: 2026-07-26

## Context

TaskControl needs a low-friction local development and demonstration database while preserving a credible path to production-grade relational deployment.

## Decision

Use SQLite for initial local development, tests, and single-node demonstrations. Design schema, queries, migrations, identifiers, transactions, and locking assumptions for PostgreSQL compatibility from the beginning. PostgreSQL is the initial production target family; CockroachDB may be evaluated later through a dedicated compatibility decision.

## Rationale

SQLite reduces setup cost and supports rapid iteration. Compatibility discipline avoids making it the accidental permanent architecture.

## Consequences

Features that only work on one engine must be isolated or avoided. Concurrency behaviour cannot be validated solely with SQLite.

## Constraints

- CI includes PostgreSQL integration coverage before production claims.
- Avoid engine-specific types and implicit coercions without adapters.
- Do not assume SQLite locking or transaction semantics represent production.
- Migration scripts are tested on every supported engine.
- JSON, timestamp, Boolean, identifier, and uniqueness behaviour are normalised explicitly.

## Review triggers

Adopting CockroachDB or another database requires an ADR covering consistency, migration, transaction, and operational consequences.
