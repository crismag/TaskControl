# Definition of Done

- Document level: **1 — Architecture**
- Lifecycle state: Canonical

A change is done only when all applicable dimensions are complete or explicitly deferred with a tracked reason.

## Product and domain

- **The recognition test.** For any change a user can see, ask: would a production engineer
  who has never seen TaskControl recognise this as automating work they currently do by
  hand? If the change is only meaningful to someone who already understands the
  architecture, it is not done — see `product/PRODUCT_PHILOSOPHY.md`.
- The intended user or operational outcome is clear.
- Domain terminology matches the handbook.
- Invariants and state transitions are implemented in the correct layer.
- Failure, skip, unknown, retry, timeout, and cancellation semantics remain distinct.
- Assumptions and deferred decisions are documented.

## Architecture

- Dependency direction is preserved.
- Business logic is absent from transport, ORM, and vendor adapters.
- New extension points and dependencies are justified.
- Cross-context interaction uses explicit contracts.
- Architectural exceptions have an ADR or tracked debt item.

## Implementation

- Code is typed, readable, and free of avoidable duplication.
- Error handling uses the approved taxonomy and preserves causes.
- Transactions, idempotency, and concurrency behaviour are explicit.
- Configuration is typed, deterministic, and documented.
- Secret values are never persisted or logged.

## Interfaces

- API, CLI, UI, worker, or adapter contracts are implemented where applicable.
- Validation and stable error responses are present.
- Compatibility and versioning implications are addressed.
- Examples or fixtures demonstrate intended use.

## Operations

- Structured logging and correlation fields are included.
- Metrics, tracing, health, and audit behaviour are added where material.
- Failure diagnosis and recovery paths are documented.
- Deployment, migration, and rollback implications are understood.

## Quality

- Appropriate domain, application, adapter, transport, UI, and end-to-end tests exist.
- Regression tests accompany defect fixes where feasible.
- Static checks and test suites pass.
- Security and privacy risks have been reviewed.
- Performance claims are measured rather than assumed.

## Knowledge

- Relevant development documentation is updated.
- Public contracts and configuration are documented.
- Implementation status identifies incomplete or blocked work.
- Changelog or migration notes are added when required.

## Final self-review

The author or agent must be able to answer:

1. What behaviour changed?
2. Which domain and architecture rules govern it?
3. How can it fail?
4. How is failure observed and recovered?
5. What proves it works?
6. What future contributor knowledge was preserved?
