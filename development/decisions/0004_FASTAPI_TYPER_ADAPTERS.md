# ADR 0004: FastAPI and Typer as Delivery Adapters

- Document level: **1 — Architecture**
- Lifecycle state: Canonical
- Status: Accepted
- Date: 2026-07-26

## Context

TaskControl needs a documented HTTP API and an operator-friendly command-line interface without creating separate business implementations.

## Decision

Use FastAPI for HTTP delivery and Typer for CLI delivery. Both are thin adapters over the same application services and domain contracts.

## Rationale

FastAPI provides typed request handling and OpenAPI support. Typer provides a consistent Python CLI. Shared application services prevent behavioural drift between interfaces.

## Consequences

Transport schemas and formatting remain adapter concerns. CLI commands must not call API endpoints merely to reuse behaviour when both can invoke application services directly in-process.

## Constraints

- Endpoints and commands validate transport input, invoke one use case, and map output.
- Authentication and request context are converted into application-level principals.
- Stable error categories map consistently across API and CLI.
- Framework objects never cross into domain contracts.

## Review triggers

A replacement framework requires evidence of material benefit and a migration ADR; application and domain behaviour should remain unaffected.
