# Engineering Laws

These laws are default constraints, not suggestions.

## 1. Architecture is not sacrificed for convenience

A faster implementation is not acceptable when it creates forbidden coupling, bypasses policy, or weakens domain ownership.

## 2. Business logic belongs to the domain or application layer

FastAPI endpoints, Typer commands, React components, SQLAlchemy models, scheduler adapters, and deployment adapters must not own business rules.

## 3. Frameworks remain at the boundary

The domain must not import FastAPI, SQLAlchemy, Typer, React, platform schedulers, cloud SDKs, or monitoring SDKs.

## 4. Important behaviour must be explainable

The system must be able to explain decisions such as configuration resolution, execution eligibility, permission denial, retry selection, result classification, and deployment drift.

## 5. Determinism is preferred over cleverness

Given the same authoritative inputs and versioned rules, TaskControl should produce the same resolved configuration, deployment plan, and decision outcome.

## 6. Hidden assumptions become documented assumptions

When requirements are incomplete, record the assumption in implementation notes or status documentation. Do not silently convert guesses into permanent behaviour.

## 7. Generated artefacts are reproducible

Generated scheduler entries, deployment bundles, configuration snapshots, and API representations must identify their source revision and generation inputs.

## 8. Security, audit, and observability cannot be bypassed

No alternate endpoint, CLI path, background job, plugin, or migration may evade permission checks, audit requirements, redaction rules, or correlation context.

## 9. Extension points are preserved deliberately

Do not remove interfaces or replace adapters with direct framework calls merely because only one implementation currently exists.

## 10. Documentation evolves with implementation

A feature is incomplete when its contracts, configuration, operations, examples, or architectural implications remain undocumented.

## 11. Behaviour changes and structural refactors are separated

A refactor should preserve behaviour. A feature change should not conceal broad unrelated restructuring.

## 12. Every change should improve repository health

Do not leave avoidable duplication, dead paths, weaker tests, hidden configuration, unexplained warnings, or new architectural drift behind.
