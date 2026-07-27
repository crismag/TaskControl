# TaskControl Product Context

- Document level: **0 — Identity**
- Lifecycle state: Canonical

This package defines the authoritative product identity, scope, audience, ecosystem boundaries, integration model, and delivery direction for TaskControl.

## Product statement

TaskControl is a standalone application software product and utility for orchestrating automated work. It provides a coherent place to define, schedule, execute, monitor, retry, approve, audit, and extend tasks across local and future distributed environments.

## Mandatory product invariant

TaskControl Core must never depend on KAE, an AI framework, or any domain-specific application. Domain products integrate through stable public interfaces.

## Documents

1. `OPERATIONAL_MODEL_AND_PRODUCT_INTENT.md` — the real operational model that inspired
   TaskControl. Read this first: it explains what everything else is productising, and it is
   binding on implementation even as the implementation evolves.
2. `PRODUCT_VISION.md` — mission, value, principles, and success criteria.
3. `PRODUCT_SCOPE.md` — owned capabilities, non-goals, and release boundaries.
4. `PRODUCT_PHILOSOPHY.md` — design philosophy and the product test applied to every feature.
5. `USERS_AND_USE_CASES.md` — target users and representative workloads.
6. `USER_JOURNEYS.md` — concrete journeys, each marked with its phase.
7. `ECOSYSTEM_BOUNDARIES.md` — relationship to KAE and other external systems.
8. `INTEGRATION_STRATEGY.md` — public integration mechanisms and compatibility rules.
9. `PRODUCT_ROADMAP.md` — implementation-first path to the first useful release.

Capability deliberately outside the current phase is not here. It is registered in `../future/DEFERRED_CAPABILITIES.md`.

## Precedence

The repository-wide precedence ladder is published once, in `../00_CONTEXT_INDEX.md` (ADR 0017). This package sits at Level 0 and therefore outranks architecture, engineering, and blueprint documents.

Where older documentation could be read as making TaskControl part of KAE or primarily an AI engineering product, that reading is wrong. Such conflicts are corrected in the affected document — never preserved as competing product definitions, and never resolved by adding another one.
