# AI Change Policy

## Purpose

AI-assisted work must remain traceable, reviewable, and bounded. The use of an AI agent does not lower engineering or review requirements.

## Change scope

An AI agent should modify only the files required by the approved task plus directly necessary tests and documentation. Broader opportunities should be reported separately unless they block correctness.

## Commit discipline

Prefer cohesive commits that each represent one understandable change. Avoid mixing:

- behavioural changes with broad refactoring;
- generated formatting churn with logic changes;
- dependency upgrades with unrelated features;
- schema redesign with transport-only work.

## Refactoring

A refactor must preserve observable behaviour unless the task explicitly includes a behaviour change. Before refactoring, identify the contract protected by tests. After refactoring, report what remained invariant.

Do not:

- collapse layers into one service for convenience;
- replace ports with direct vendor calls;
- duplicate business rules in a new interface;
- remove extension points without an approved architectural decision;
- rename domain terms without updating the ubiquitous language and migration impact.

## Generated code

Generated code or artefacts must identify their generator and source inputs where practical. Generated files should not be manually edited unless the repository clearly defines an override mechanism.

## Dependencies

An agent must not add a production dependency merely because it is familiar or convenient. Follow the dependency evaluation requirements in `repository/11_DEPENDENCY_RULES.md`.

## Documentation

The same change must update all affected contracts, examples, configuration references, migration notes, and implementation status. Documentation-only claims must match actual repository state.

## Reviewability

The pull request description must include:

- outcome and scope;
- key design decisions;
- architectural and domain impact;
- test evidence;
- security, migration, and compatibility considerations;
- assumptions, limitations, and follow-ups.

## Human authority

AI may propose decisions, but material changes to product scope, domain semantics, public compatibility, security policy, repository architecture, or engineering governance require explicit human review.
