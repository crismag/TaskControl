# ADR 0003: Domain-First Layered Architecture

- Document level: **1 — Architecture**
- Lifecycle state: Canonical
- Status: Accepted
- Date: 2026-07-26

## Context

TaskControl must keep operational rules stable while web, CLI, persistence, schedulers, and deployment technologies evolve.

## Decision

Adopt inward dependency flow: delivery adapters depend on application services; application services depend on domain contracts; infrastructure implements ports defined inward. The domain remains framework-independent.

## Rationale

This isolates business behaviour, makes rules testable without external systems, and prevents frameworks or schemas from becoming the application model.

## Consequences

Mapping code and interfaces add deliberate structure. Simple changes may touch multiple layers, but the separation protects long-term maintainability.

## Constraints

- No FastAPI, Typer, SQLAlchemy, React, cloud, or scheduler imports in domain code.
- Endpoints and CLI commands contain no business rules.
- ORM entities are persistence representations, not domain objects.
- Application services coordinate use cases and transactions.

## Validation

Dependency tests and review must detect outward imports, transport logic in the domain, and direct database access from delivery layers.
