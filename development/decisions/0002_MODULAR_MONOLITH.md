# ADR 0002: Modular Monolith as the Initial Architecture

- Document level: **1 — Architecture**
- Lifecycle state: Canonical
- Status: Accepted
- Date: 2026-07-26

## Context

TaskControl has multiple bounded contexts but does not yet have proven scale, independent team ownership, or operational requirements that justify distributed services.

## Decision

Build the initial application as a modular monolith with explicit bounded contexts, internal interfaces, and enforceable dependency rules. Deploy it as one control-plane application while preserving seams that could support later extraction.

## Rationale

A modular monolith provides transactional simplicity, easier debugging, lower deployment cost, and faster feature integration while retaining architectural discipline. Premature microservices would add networking, observability, consistency, and release complexity without evidence.

## Consequences

Modules share a process and initial database deployment. Boundaries must be enforced by code organisation and tests rather than network separation. Large modules may later be extracted only after measured need.

## Implementation constraints

- No direct cross-module persistence access.
- Cross-context behaviour uses application contracts or domain events.
- Composition occurs at application entry points.
- Module ownership and dependencies remain documented.

## Review triggers

Independent scaling, isolation, release cadence, regulatory boundaries, or team ownership may justify extracting a module through a new ADR.
