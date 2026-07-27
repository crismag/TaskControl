> **STATUS: SUPERSEDED** — replaced by `development/10_IMPLEMENTATION_BLUEPRINT.md`.
>
> Retained for historical reasoning. **Do not use for new implementation.**
>
> Superseded: 2026-07-26. Reason: Predates the PR #7 repositioning: built around cron-artefact deployment in the first release, which ADR 0018 moved to Phase 2. Proposed a fourth repository layout, resolved by ADR 0015. Replaced by the wave-structured construction manual.

---

# Full Application Blueprint

## Objective

This document defines the target shape Claude or Codex should attempt when asked to generate a complete TaskControl application. The first generated application does not need every enterprise feature, but it must be coherent, runnable, testable, and structured so later features fit naturally.

## Architectural style

Use a Python modular monolith for the initial implementation.

The application should run as one deployable server with clear internal modules. Avoid premature microservices. Module boundaries must be strong enough that workers, agents, or services can later be separated without rewriting the domain.

## Initial applications

- `taskcontrol-api`: FastAPI HTTP API.
- `taskctl`: Typer-based command-line interface.
- `taskcontrol-worker`: background execution and deployment worker, initially runnable in-process or as a separate process.
- `taskcontrol-web`: TypeScript web interface, preferably React with Vite.

## Recommended repository layout

```text
TaskControl/
├── pyproject.toml
├── README.md
├── LICENSE
├── Makefile
├── docker-compose.yml
├── .env.example
├── apps/
│   ├── api/
│   ├── cli/
│   ├── worker/
│   └── web/
├── src/taskcontrol/
│   ├── domain/
│   ├── application/
│   ├── scheduling/
│   ├── execution/
│   ├── deployment/
│   ├── profiles/
│   ├── calendars/
│   ├── conditions/
│   ├── expectations/
│   ├── inventory/
│   ├── notifications/
│   ├── audit/
│   ├── plugins/
│   ├── persistence/
│   └── infrastructure/
├── adapters/
│   ├── schedulers/
│   │   ├── cron/
│   │   └── systemd/
│   ├── executors/
│   │   ├── shell/
│   │   ├── python/
│   │   ├── tcl/
│   │   ├── executable/
│   │   └── http/
│   ├── deployment/
│   │   ├── local/
│   │   └── ssh/
│   └── monitoring/
├── schemas/
├── examples/
├── migrations/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   └── end_to_end/
└── development/
```

The exact folder arrangement may be adjusted when justified, but preserve dependency direction.

## Dependency direction

1. Domain modules depend only on Python standard library and narrowly approved domain libraries.
2. Application services depend on domain abstractions.
3. Adapters depend on application and domain interfaces.
4. API and CLI call application services.
5. Persistence implements repositories defined inward.
6. Web UI communicates through the API.
7. No domain rule belongs solely in an API route, CLI command, React component, or ORM model.

## Core functional vertical slice

The generated application should implement a complete local workflow:

1. Create, read, update, archive, and version a Task.
2. Define a cron-like schedule through structured fields and optional advanced expression.
3. Attach a runtime profile with non-secret environment values and secret references.
4. Attach run conditions, initially enabled switch and weekday/calendar checks.
5. Validate the task and produce explainable validation results.
6. Generate an execution package and a cron deployment artefact.
7. Preview a deployment plan.
8. Apply or remove the local deployment safely.
9. Execute the task manually through the same runtime used by scheduler wrappers.
10. Capture stdout, stderr, exit code, timing, status, skip reason, retries, and expectation results.
11. Display task definitions, deployment state, and execution history in CLI, API, and web UI.

## Domain entities

At minimum implement:

- Task
- TaskRevision
- Schedule
- ExecutionSpecification
- RuntimeProfile
- RunCondition
- Calendar
- Target
- Deployment
- DeploymentPlan
- GeneratedArtifact
- Execution
- ExecutionAttempt
- Expectation
- ExpectationResult
- NotificationRule
- AuditEvent

Entities should use UUIDs, explicit timestamps, and version fields where concurrency matters.

## Initial persistence

- SQLite must work out of the box.
- PostgreSQL should be supported through configuration.
- Use SQLAlchemy 2.x and Alembic.
- Keep ORM models separate from domain objects when practical.
- Use repository and unit-of-work patterns lightly; avoid needless ceremony.

## API

Provide versioned endpoints under `/api/v1`.

Minimum groups:

- health and readiness;
- tasks and revisions;
- profiles;
- calendars;
- targets;
- validation;
- deployment plans and deployments;
- manual executions;
- execution history and logs;
- adapter capability discovery.

Use Pydantic request and response schemas. Return structured errors with stable codes, human-readable messages, field details, and correlation IDs.

## CLI

The CLI must be a first-class client of application services or the API, not a duplicate implementation.

Representative commands:

```text
taskctl init
taskctl server
taskctl task create
taskctl task list
taskctl task show <id>
taskctl task validate <id>
taskctl task run <id>
taskctl plan create <task-id> --target local
taskctl plan show <plan-id>
taskctl deploy apply <plan-id>
taskctl deploy remove <deployment-id>
taskctl execution list
taskctl execution show <id>
taskctl adapters list
```

## Web UI

Build an operational interface rather than a decorative dashboard.

Minimum pages:

- Overview
- Tasks
- Task editor with sections for command, schedule, profile, conditions, retry, timeout, expectations, and target
- Validation and generated artefact preview
- Deployment plan diff
- Deployments
- Execution history
- Execution detail with logs and decisions
- Profiles
- Calendars
- Settings and adapter capabilities

The UI must surface resolved values and origins when inheritance is introduced.

## Runtime engine

The runtime should:

1. Load an immutable task revision or deployment snapshot.
2. Resolve the runtime profile.
3. Evaluate run conditions in deterministic order.
4. Return a structured skip or block result when disallowed.
5. Acquire a concurrency lock.
6. Launch the execution adapter without unsafe shell interpolation.
7. Stream and persist logs.
8. enforce timeout and cancellation.
9. classify exit result.
10. evaluate expected outcomes.
11. apply retry policy only to eligible outcomes.
12. persist final status and audit events.

## Adapters

Every adapter should expose metadata and capabilities. Unsupported options must produce validation errors before deployment.

Initial required adapters:

- cron scheduler;
- local deployment;
- shell executor;
- Python executor;
- executable executor.

Recommended additional adapters if time permits:

- systemd timer;
- Tcl executor;
- HTTP executor;
- SSH deployment;
- webhook notification.

## Security baseline

- Do not store plaintext secrets in task definitions.
- Use secret references and a provider interface.
- Redact secrets from logs, previews, API payloads, and errors.
- Validate filesystem paths and command arguments.
- Avoid `shell=True` by default.
- Restrict local deployment paths.
- Add basic authentication boundaries even if the first local edition defaults to a single administrator.
- Record security-sensitive actions in audit events.

## Testing baseline

The generated application is incomplete unless tests run.

Required:

- domain unit tests;
- schedule and condition tests with time zones;
- runtime success, failure, timeout, skip, retry, and expectation tests;
- adapter contract tests;
- API integration tests;
- SQLite migration test;
- one end-to-end local task deployment and execution test;
- frontend component or smoke tests.

## Developer experience

Provide:

- one-command local setup;
- sample tasks;
- `.env.example`;
- database migration command;
- lint, format, type-check, test, and run commands;
- Docker Compose for PostgreSQL and optional services;
- clear README instructions;
- architecture notes for generated assumptions.

## Completion definition

A full-application attempt is successful when a new contributor can clone the repository, install dependencies, initialise the database, start the API and UI, create a task, validate it, run it manually, preview and apply a local cron deployment, inspect execution history, and run the automated test suite.

Enterprise placeholders without working local behaviour do not satisfy this objective.
