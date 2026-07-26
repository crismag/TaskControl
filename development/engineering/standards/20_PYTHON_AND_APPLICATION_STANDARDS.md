# Python and Application Standards

## General expectations

- Support the Python version declared by the project; do not rely on undeclared interpreter behaviour.
- Use complete type hints for public functions, methods, attributes, and application contracts.
- Prefer descriptive names over abbreviations and single-letter variables.
- Keep functions focused and make side effects visible.
- Prefer immutable value objects for identifiers, snapshots, money-like values, time ranges, and resolved decisions.
- Use dataclasses or plain domain classes for domain concepts; use Pydantic primarily at validation and transport boundaries.
- Do not use dictionaries as permanent substitutes for stable domain types.

## Application services

An application service represents a use case. It should:

1. validate authorisation and command-level prerequisites;
2. load required aggregates through ports;
3. invoke domain behaviour;
4. persist changes within an explicit transaction boundary;
5. append audit information;
6. publish events only after durable state is secured;
7. return a transport-neutral result.

Application services should not:

- parse HTTP requests;
- format CLI output;
- issue vendor-specific queries;
- implement aggregate invariants;
- leak ORM objects.

## Async usage

Use asynchronous code when waiting on genuinely asynchronous I/O and when the surrounding stack benefits. Do not make pure domain logic async. Avoid blocking calls inside an event loop. Thread or process offloading must be explicit and bounded.

## Exceptions

Define a stable exception taxonomy:

- validation errors;
- domain rule violations;
- authorisation failures;
- not-found and conflict errors;
- configuration errors;
- transient infrastructure failures;
- permanent infrastructure failures;
- execution and deployment errors.

Do not catch broad exceptions unless translating at a boundary, adding context, or ensuring cleanup. Preserve the original cause.

## Time and identifiers

- Inject clocks where time affects decisions.
- Store timestamps in UTC and preserve declared business time zones separately.
- Generate identifiers through an injectable abstraction where deterministic tests benefit.

## Configuration

Configuration must be typed, validated at startup, layered according to the domain handbook, and explainable. Do not scatter environment-variable reads throughout business code.

## Code comments and documentation

Comments explain intent, constraints, or non-obvious trade-offs. They must not narrate obvious syntax. Public modules and contracts require concise docstrings describing responsibilities and failure behaviour.
