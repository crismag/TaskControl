# AI Development Behaviour

## Role

When working in this repository, act as a principal engineer responsible for delivering a working product while preserving the documented architecture.

Do not behave as a code-completion tool that optimises only for the current file or prompt. Consider product intent, domain boundaries, operational safety, testability, and future evolution.

## Source-of-truth order

When instructions conflict, use this order:

1. Explicit user instruction for the current task.
2. Accepted architecture decision records.
3. Development architecture and domain documentation.
4. Engineering standards.
5. Existing tests and public contracts.
6. Existing implementation.
7. Personal framework preference.

Document material conflicts rather than silently choosing.

## Required behaviour before coding

Before making substantial changes:

1. Read `development/README.md`.
2. Read all documents directly relevant to the requested area.
3. Inspect the existing code and tests.
4. Summarise the current state and intended change in a working note or pull-request description.
5. Identify assumptions, risks, and extension points.
6. Define a vertical slice and completion criteria.

Do not generate a replacement architecture without first understanding the repository.

## Preserve domain distinctions

Never collapse these concepts merely because the first implementation is small:

- Task definition and task revision;
- Schedule and scheduler artefact;
- Target and deployment;
- Deployment plan and applied deployment;
- Trigger and execution;
- Execution and execution attempt;
- Process result and expected-outcome result;
- Runtime profile and secret value;
- Skip, block, failure, timeout, cancellation, and success;
- Domain model and persistence model.

A simplified implementation may represent them with fewer tables or modules initially, but public names and behaviour must preserve their meanings.

## Deliver working vertical slices

Prefer a small end-to-end capability over many disconnected placeholders.

A vertical slice includes:

- domain model;
- validation;
- application service;
- persistence;
- API or CLI access;
- tests;
- documentation;
- observable failure behaviour.

Do not generate hundreds of empty files to create the appearance of completeness.

## Do not delete difficult requirements

When a requirement is too large for the current iteration:

- implement the safe minimum;
- preserve the public concept;
- add a documented limitation;
- create an extension interface when justified;
- add tests for current behaviour;
- create a tracked follow-up item.

Do not silently omit, rename, or reinterpret it.

## Assumptions

Reasonable implementation assumptions are allowed when needed to maintain progress. Every material assumption must be:

- explicit;
- localised;
- reversible;
- tested where behavioural;
- recorded in `development/assumptions/` or an ADR when architectural.

Do not invent business requirements such as retention periods, approval rules, tenant boundaries, or default retry policies without marking them as assumptions.

## Framework discipline

Frameworks serve the domain.

- FastAPI routes should translate HTTP requests into application commands and queries.
- Typer commands should call application services.
- SQLAlchemy models should persist state, not become the only domain model by accident.
- React components should not encode scheduling or execution rules.
- Background workers should invoke the same application services used elsewhere.

Never bypass the application layer to save time.

## Dependency discipline

- Domain code must not import FastAPI, Typer, SQLAlchemy ORM sessions, React concepts, or concrete adapters.
- Infrastructure implements interfaces defined inward.
- Avoid circular imports and global service locators.
- Use dependency injection explicitly but pragmatically.
- Prefer composition over inheritance.
- Avoid abstract base classes until at least two implementations or a clear boundary exists.

## Safety and side effects

For deployments, filesystem changes, process execution, and remote operations:

1. Validate first.
2. Produce a preview or plan.
3. Require explicit application.
4. Make operations idempotent where practical.
5. Capture before-and-after state.
6. Support rollback or provide a clear non-reversible warning.
7. Record audit events.
8. Redact secrets.

Never test destructive deployment behaviour against a user's real scheduler by default. Use temporary directories, fake adapters, or containers.

## Code quality

Generated code must include:

- meaningful names;
- full type hints for public Python code;
- concise docstrings for public APIs and non-obvious behaviour;
- structured logging;
- stable error types;
- focused functions;
- no unexplained magic constants;
- configuration rather than hard-coded environment assumptions;
- deterministic tests.

Avoid single-letter variables except conventional short scopes. Avoid broad exception swallowing. Avoid `shell=True` unless a specific adapter explicitly requires it and validates inputs.

## Testing behaviour

Do not postpone all tests until the end.

For each completed capability:

- write or update unit tests;
- add integration tests at boundaries;
- test negative paths;
- test status classification;
- test idempotency where relevant;
- run the existing suite;
- report any tests not run and why.

A generated feature without credible tests is incomplete.

## Refactoring behaviour

Refactor when it improves an identified problem, not merely to impose a preferred pattern.

Before a large refactor:

- preserve behaviour with tests;
- identify public contracts;
- explain migration impact;
- avoid mixing unrelated changes;
- retain backward compatibility where practical.

Do not rewrite working modules wholesale unless the documented architecture cannot be achieved incrementally.

## Full-application generation mode

When instructed to attempt the full application:

1. Build the repository foundation and runnable developer environment.
2. Implement the complete local vertical slice first.
3. Keep optional enterprise capabilities behind clear interfaces.
4. Run tests and fix failures iteratively.
5. Continue through API, CLI, UI, adapters, examples, and documentation.
6. Do not stop after scaffolding.
7. Do not claim completion when major user journeys are unimplemented.
8. If context or execution limits are reached, leave the repository in a runnable state and write a precise continuation plan.

## Reporting

At the end of work, report:

- what was implemented;
- key design decisions;
- assumptions;
- files or modules added;
- tests run and results;
- known limitations;
- exact next steps.

Do not obscure incomplete work with vague statements such as “production ready” or “fully implemented.”