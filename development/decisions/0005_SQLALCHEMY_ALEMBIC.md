# ADR 0005: SQLAlchemy and Alembic for Persistence

- Status: Accepted
- Date: 2026-07-26

## Context

TaskControl needs relational persistence, explicit transactions, repeatable migrations, SQLite development support, and a path to PostgreSQL-compatible production databases.

## Decision

Use SQLAlchemy for relational persistence adapters and Alembic for schema migrations. Persistence models remain separate from domain objects and are translated through repositories.

## Rationale

The combination provides mature Python tooling, explicit SQL control when needed, database portability, and versioned migration workflows.

## Consequences

Mapping code is required. ORM convenience must not override aggregate boundaries or domain invariants. Database-specific behaviour must be isolated and tested across supported engines.

## Constraints

- Application services own transaction boundaries.
- Repositories do not commit independently unless explicitly designed.
- Every production schema change has a reviewed migration.
- Migrations preserve audit and revision history.
- ORM lazy loading must not leak into domain behaviour.

## Review triggers

Reconsider only if measured limitations, database requirements, or operational constraints materially outweigh migration cost.
