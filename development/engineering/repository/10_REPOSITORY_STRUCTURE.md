# Repository Structure

- Document level: **1 — Architecture**
- Lifecycle state: Canonical

The repository should make ownership and dependency direction visible.

## Recommended top-level shape

```text
src/taskcontrol/
  apps/             # composition roots and executable entry points
    api/            #   builds and starts the ASGI application
    cli/            #   builds and starts the CLI
    worker/         #   (Phase 3) builds and starts the worker
  domain/           # entities, value objects, policies, domain services
  application/      # use cases, commands, queries, orchestration
  ports/            # interfaces required by application/domain
  adapters/         # database, scheduler, executor, notification integrations
  api/              # HTTP transport and schemas
  cli/              # CLI transport
  infrastructure/   # configuration, logging, persistence setup, runtime wiring
  common/           # cross-cutting stable utilities and the error taxonomy
web/                # React application
migrations/         # Alembic
schemas/            # exported JSON Schema for portable definitions
examples/           # runnable sample task definitions
tests/              # tests mirroring production boundaries
docs/               # user and developer documentation
development/        # authoritative project knowledge
```

This is the single normative statement of the tree (ADR 0015). Composition roots sit inside the installed package so console scripts and ASGI factories resolve from a wheel (ADR 0019). Actual names may evolve through further ADRs, but responsibilities must remain equivalent.

## Directory responsibilities

### `apps/`

Contains executable entry points and dependency composition only. `apps/api` and `apps/cli` **wire**; `api/` and `cli/` **transport**. A router or a command body in `apps/` is misplaced.

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
