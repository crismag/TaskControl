# TaskControl Product Context

This package defines the authoritative product identity, scope, audience, ecosystem boundaries, integration model, and delivery direction for TaskControl.

## Product statement

TaskControl is a standalone application software product and utility for orchestrating automated work. It provides a coherent place to define, schedule, execute, monitor, retry, approve, audit, and extend tasks across local and future distributed environments.

## Mandatory product invariant

TaskControl Core must never depend on KAE, an AI framework, or any domain-specific application. Domain products integrate through stable public interfaces.

## Documents

1. `PRODUCT_VISION.md` — mission, value, principles, and success criteria.
2. `PRODUCT_SCOPE.md` — owned capabilities, non-goals, and release boundaries.
3. `USERS_AND_USE_CASES.md` — target users and representative workloads.
4. `ECOSYSTEM_BOUNDARIES.md` — relationship to KAE and other external systems.
5. `INTEGRATION_STRATEGY.md` — public integration mechanisms and compatibility rules.
6. `PRODUCT_ROADMAP.md` — implementation-first path to the first useful release.

## Precedence

When older documentation can be interpreted as making TaskControl part of KAE or primarily an AI engineering product, this product package takes precedence. Such conflicts should be corrected in the affected document rather than preserved as competing product definitions.