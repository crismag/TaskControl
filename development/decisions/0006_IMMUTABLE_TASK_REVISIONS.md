# ADR 0006: Immutable Task Revisions

- Status: Accepted
- Date: 2026-07-26

## Context

Task definitions evolve, but executions, deployments, audits, and investigations must remain reproducible and explainable.

## Decision

Separate stable Task identity from immutable TaskRevision content. Any execution-relevant change creates a new revision. Executions and deployment plans reference the exact revision used.

## Rationale

Mutable definitions would make historical behaviour ambiguous and weaken audit, rollback, and reproducibility.

## Consequences

Revision storage grows and editing becomes publish-new-revision rather than in-place mutation. User interfaces must clearly distinguish draft, published, active, and historical revisions.

## Constraints

- Published revisions are immutable.
- Schedules may point to a pinned revision or an explicit current-revision policy.
- Historical executions never resolve through a newer revision.
- Revision creation records actor, timestamp, and change summary.

## Review triggers

Retention or compaction may be introduced later, but must preserve reconstructability and audit evidence.
