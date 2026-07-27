# Incremental Implementation Playbook

- Document level: **3 — Specifications**
- Lifecycle state: Canonical

## Objective

Produce the smallest coherent change that delivers verified behaviour while preserving TaskControl's domain model and architectural boundaries.

## Implementation order

Work from stable policy towards replaceable mechanisms:

1. Add or change domain concepts and invariants.
2. Add application commands, queries, and orchestration.
3. Define or extend ports at the layer that owns the need.
4. Implement persistence and external adapters.
5. Expose behaviour through API, CLI, or UI adapters.
6. Add observability, audit, configuration, and operational controls.
7. Update tests and documentation with each increment.

## Change discipline

- Keep business decisions out of FastAPI routes, Typer commands, React components, ORM models, scheduler callbacks, and cloud SDK code.
- Reuse established repository patterns unless they are demonstrably inadequate.
- Name concepts using the domain handbook.
- Make state transitions explicit and validated.
- Keep transaction boundaries visible in application services.
- Preserve deterministic behaviour and explainable configuration.
- Avoid hidden network, filesystem, process, or database activity in domain code.
- Do not broaden public interfaces without a documented requirement.

## Vertical-slice loop

For each increment:

1. State the behaviour being added.
2. Add or update a failing test where practical.
3. Implement the minimum required inner-layer behaviour.
4. Add outer adapters only when the use case requires them.
5. Run focused tests.
6. Review the diff for unrelated changes.
7. Commit a coherent unit with an explanatory message.

## Data changes

Schema changes require:

- an Alembic migration;
- forward and rollback reasoning;
- compatibility assessment for SQLite and PostgreSQL targets;
- indexes and constraints justified by invariants or queries;
- a test or verification procedure.

Never edit migration history already used outside disposable development environments.

## Completion signal

An implementation increment is complete when its behaviour is accessible through the intended boundary, verified by tests, observable enough to diagnose, documented where required, and leaves no known broken intermediate architecture.
