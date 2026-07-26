# ADR 0009: Deterministic Layered Configuration

- Document level: **1 — Architecture**
- Lifecycle state: Canonical
- Status: Accepted
- Date: 2026-07-26

## Context

TaskControl configuration can originate from product defaults, environment settings, profiles, task revisions, deployment context, and runtime overrides. Silent precedence would make execution difficult to diagnose.

## Decision

Resolve configuration through an explicit, ordered precedence model. Preserve the source and transformation history of every effective value. Secrets remain references until the execution or deployment boundary.

## Rationale

Deterministic and explainable configuration is essential for reproducibility, audit, support, and safe automation.

## Consequences

Resolution metadata increases implementation and storage complexity. Interfaces must expose effective values without revealing secret material.

## Constraints

- Precedence order is documented and tested.
- Unknown or conflicting values fail explicitly where required.
- Runtime overrides are permission-controlled and audited.
- Secret values are never stored in resolved configuration snapshots.
- Historical runs retain safe provenance sufficient to reconstruct decisions.

## Review triggers

New configuration layers require an ADR update or a new ADR defining precedence and compatibility.
