# Repository Structure

The repository should make ownership and dependency direction visible.

## Recommended top-level shape

```text
apps/              # composition roots and executable entry points
src/taskcontrol/
  domain/           # entities, value objects, policies, domain services
  application/      # use cases, commands, queries, orchestration
  ports/            # interfaces required by application/domain
  adapters/         # database, scheduler, executor, notification integrations
  api/              # HTTP transport and schemas
  cli/              # CLI transport
  infrastructure/   # configuration, logging, persistence setup, runtime wiring
web/                # React application
tests/              # tests mirroring production boundaries
development/        # authoritative project knowledge
```

Actual names may evolve through ADRs, but responsibilities must remain equivalent.

## Directory responsibilities

### `apps/`

Contains executable entry points and dependency composition only.

Allowed:

- construct settings;
- configure logging;
- instantiate adapters and services;
- start API, CLI, worker, or scheduler processes.

Forbidden:

- business rules;
- direct persistence queries for user operations;
- duplicated orchestration.

### `domain/`

Owns business vocabulary, invariants, state transitions, policies, and pure decision logic.

Preferred dependencies: Python standard library and deliberately approved lightweight utilities.

### `application/`

Coordinates use cases, transactions, ports, policy checks, and domain operations. It does not own transport or vendor details.

### `ports/`

Defines interfaces required by the inner layers: repositories, clocks, ID generation, schedulers, executors, secret resolution, notifications, and audit sinks.

Ports are consumer-owned contracts. Adapters conform to them.

### `adapters/`

Translate between TaskControl contracts and external technologies. Adapters may contain vendor-specific failure mapping and serialisation but not domain policy.

### `api/` and `cli/`

Translate input into application requests and translate application results into transport-specific responses. They must share application services rather than reimplement behaviour.

### `infrastructure/`

Owns bootstrapping, configuration loading, database engine creation, telemetry wiring, and process-level concerns.

### `web/`

Owns presentation, client state, accessibility, and API interaction. It must not duplicate authoritative domain decisions that belong on the server.

## Placement rule

Place code according to the responsibility it owns, not according to which feature first needed it.

## Shared code

A `shared` or `common` module is permitted only for genuinely cross-cutting, stable concepts. It must not become a dumping ground for misplaced domain behaviour.
