# TaskControl Implementation Blueprint

- Document level: **2 — Blueprint**
- Status: Authoritative
- Governs: `development/specifications/`, `development/prompts/`, all source code
- Governed by: `product/PRODUCT_SCOPE.md`, `product/PRODUCT_ROADMAP.md`, `decisions/`
- Last reconciled: 2026-07-26

## What this document is

This is the construction manual. It is not vision, not architecture, and not roadmap. It answers exactly one question:

> Given today's repository, what do we build next?

It is the only document in the repository that answers it. When code lands, this document is updated in the same pull request. A wave is not complete until its entry here reflects reality.

## What this document is not

It does not restate the directory tree (see `engineering/repository/10_REPOSITORY_STRUCTURE.md`), the outcome taxonomy (see ADR 0016), domain semantics (see `domain/`), or product scope (see `product/PRODUCT_SCOPE.md`). Where it needs those, it links.

## Current position

**Repository state: Wave 0 complete. The project installs, lints, type-checks, and tests
green. No product behaviour beyond version and health.**

**Next action: Wave 1 — Domain core.**

| Wave | Name | Status |
| --- | --- | --- |
| 0 | Foundation and quality gates | **complete** (2026-07-26) |
| 1 | Domain core | not started |
| 2 | Persistence and migrations | not started |
| 3 | Runtime and executors | not started |
| 4 | Expectations and outcome evaluation | not started |
| 5 | Scheduling, eligibility, and dependencies | not started |
| 6 | Application services and audit | not started |
| 7 | REST API v1 | not started |
| 8 | CLI | not started |
| 9 | Web interface | not started |
| 10 | Approvals, recovery, and release readiness | not started |

Waves 0–4 constitute the **first usable milestone**: a task can be defined, run, and inspected with honest outcomes. Waves 0–10 constitute **Phase 1** of `product/PRODUCT_ROADMAP.md`.

## Scope boundary for Phase 1

Per ADR 0018, TaskControl executes work itself in Phase 1 through an internal scheduler. There is one target, `local`.

**In Phase 1:** task definitions and immutable revisions; manual and scheduled execution; run conditions and dependency eligibility; retries, timeouts, cancellation; attempts, outcomes, logs, history; expectations; audit; approvals; REST API, CLI, web UI; persistence with restart recovery.

**Not in Phase 1:** generated scheduler artefacts, crontab or systemd writing, deployment plan/apply, drift detection, remote targets or workers, inventory groups, RBAC beyond a single administrator, notifications beyond a logging sink, plugin loading from third-party packages. These are Phase 2+ and are registered in `future/DEFERRED_CAPABILITIES.md`. Their **ports** are defined in Phase 1; their implementations are not.

**No Phase 1 code writes to a user crontab or any host scheduler configuration.**

## Rules that apply to every wave

1. The repository is runnable and green at the end of every wave. `make check` passes.
2. Tests are written during the wave, not after it.
3. A wave does not implement a later wave's capability. If you need it, stub the port and record it.
4. Every wave updates this document's status table and any affected Level 0/1 document.
5. Deferred work goes in `future/DEFERRED_CAPABILITIES.md` or `OPEN_QUESTIONS.md`, never in scattered `TODO` comments.
6. No mock data behind a real interface. An endpoint that cannot yet answer returns a documented error, not a fabricated result.

---

## Wave 0 — Foundation and quality gates

**Goal:** a clean clone installs, lints, type-checks, tests, and reports its version.

### Build

- `pyproject.toml` — Python 3.12+, `src/` layout, console script `taskctl`, dependency groups for `api`, `dev`.
- `src/taskcontrol/__init__.py` with `__version__`.
- `src/taskcontrol/common/` — result and error base types, `TaskControlError` hierarchy.
- `src/taskcontrol/infrastructure/settings.py` — Pydantic settings, env-prefixed, no import-time resolution.
- `src/taskcontrol/infrastructure/logging.py` — structured logging, correlation-id support, secret-redacting filter.
- `apps/cli/main.py` — Typer app exposing `taskctl version` and `taskctl health`.
- `apps/api/main.py` — FastAPI application factory exposing `/api/v1/health` and `/api/v1/ready`.
- `tests/unit/test_architecture.py` — import-graph test enforcing `engineering/repository/11_DEPENDENCY_RULES.md`.
- `Makefile` — `install`, `format`, `lint`, `typecheck`, `test`, `check`, `run-api`, `run-web`.
- `.github/workflows/ci.yml` — matrix on 3.12/3.13, runs `make check`.
- `.env.example`, `docs/DEVELOPMENT.md`.

### Acceptance

- Clean clone → `make install && make check` passes with zero warnings.
- `taskctl version` prints the package version; `taskctl health` exits 0.
- `GET /api/v1/health` returns 200 with version and status.
- The architecture test fails when a forbidden import is added deliberately.
- No product behaviour beyond version and health.

**Gate:** CI green on a pull request from a clean checkout.

### Outcome

Delivered as specified, with three deviations worth carrying forward:

1. **ADR 0019** was raised during the wave. ADR 0015 placed composition roots in a
   top-level `apps/`, which is absent from an installed wheel, so neither the `taskctl`
   console script nor the ASGI factory could resolve outside a source checkout. Composition
   roots moved to `src/taskcontrol/apps/`. A CI job now installs a built wheel into a clean
   environment and runs both, so the claim stays proven.
2. **Unrecognised `TASKCONTROL_*` variables are rejected.** A mistyped variable was
   silently ignored, which is precisely the failure mode this product exists to remove from
   scheduled operations. `load_settings` now fails with the variable name — never its value,
   which may be secret.
3. **HTTP status constants are literal integers**, not framework constants, which have
   already been renamed once upstream.

Beyond the listed scope, Wave 0 also delivered the error taxonomy (`common/errors.py`),
correlation middleware, and API error rendering, because the health endpoints and the CLI
both needed a stable failure contract to be testable.

Verified: `make check` green; 80 tests; 96% statement coverage; `taskctl version` and
`taskctl health` exit 0; `GET /api/v1/health` and `/api/v1/ready` return 200; invalid
configuration exits 78; the architecture test was confirmed to fail on a deliberately
planted forbidden import and pass once removed.

---

## Wave 1 — Domain core

**Goal:** the vocabulary of the product exists as typed, tested, framework-free code.

### Build

`src/taskcontrol/domain/`:

- `common/` — `EntityId` (UUIDv7), `RevisionNumber`, `ContentDigest`, `UtcTimestamp`, `Duration`, `TimeZone` (IANA-validated), `CorrelationId`, `IdempotencyKey`, `SecretReference`. No unvalidated dictionaries cross a domain boundary.
- `tasks/` — `Task`, `TaskRevision`, `ExecutionSpecification`, lifecycle states and legal transitions per `domain/01`.
- `execution/` — `ExecutionState`, `ExecutionOutcome`, `ReasonCode` registry, `ProcessResult`, `RetryPolicy`, `TimeoutPolicy`, exactly as ADR 0016 defines them.
- `configuration/` — `Profile`, `Variable`, `SecretReference`, layer ordering, `ResolutionTrace`.
- `scheduling/` — `Schedule` value objects (interval, weekday-time, cron expression), `RunCondition` types, `Calendar`.
- `policies/` — pure functions: outcome classification, retry eligibility, configuration resolution.

Plus `schemas/` JSON Schema export and `examples/` with two runnable sample task definitions.

### Acceptance

- Every value object rejects invalid input with a typed error carrying a machine-readable code.
- A task revision is immutable once published; editing produces a new revision.
- Configuration resolution returns value, source layer, and secret flag for every key.
- Outcome classification is a pure function with a parameterised test over every ADR 0016 member.
- Round-trip: YAML → domain → YAML is stable and byte-identical for the examples.
- `domain/` imports nothing outside the standard library. Enforced by the Wave 0 architecture test.

**Gate:** domain unit-test coverage of invariants, including negative cases for every validation rule.

---

## Wave 2 — Persistence and migrations

**Goal:** definitions and history survive a restart.

### Build

- `src/taskcontrol/ports/repositories.py` — repository interfaces owned by the application layer.
- `src/taskcontrol/adapters/persistence/` — SQLAlchemy 2 models kept separate from domain objects, with explicit mappers.
- `migrations/` — Alembic environment and the initial revision.
- Unit-of-work helper in `infrastructure/`.
- `taskctl init` creates the database and runs migrations.

### Acceptance

- SQLite works with no configuration. PostgreSQL works by changing one setting.
- All timestamps stored in UTC; no naive datetime reaches the database.
- Migration up and down both succeed on an empty and a populated database.
- Repository contract tests run against both backends; PostgreSQL tests are skipped with a clear message when unavailable.
- No SQLAlchemy import appears under `domain/` or `application/`.

**Gate:** a migration test that creates, migrates, writes, restarts, and reads back.

---

## Wave 3 — Runtime and executors

**Goal:** TaskControl runs real work and classifies the result honestly.

### Build

- `src/taskcontrol/ports/executor.py` — executor port with capability metadata.
- `src/taskcontrol/adapters/executors/` — `shell`, `python`, `executable`. Argument arrays only; `shell=True` requires explicit opt-in in the task definition and is recorded in the audit event.
- `src/taskcontrol/application/runtime/` — the single execution entry point used by every caller: create execution, resolve configuration, acquire lock, launch attempt, stream and persist output, enforce timeout, terminate, classify, apply retry policy, persist.
- Overlap locking, working directory, environment resolution, stdout/stderr captured separately with a combined view.
- `taskctl run <task-id>` and manual execution.

### Acceptance

- Success, non-zero exit, launch failure, timeout with termination, cancellation, and lock contention each produce the correct ADR 0016 outcome and reason code.
- Retries occur only for eligible outcomes and stop at the configured limit; each attempt is a separate persisted record.
- Secrets never appear in stdout capture, logs, audit events, or error messages. Tested with a canary value.
- A killed process leaves a terminal execution, never a permanently `RUNNING` one.
- The runtime is entered identically from CLI and application service.

**Gate:** integration tests using real subprocesses, including a deliberate timeout and a deliberate SIGKILL.

---

## Wave 4 — Expectations and outcome evaluation

**Goal:** a zero exit code stops meaning success by default.

### Build

- `domain/expectations/` — `Expectation`, `ExpectationResult`, evaluator port.
- Evaluators: expected exit codes, file exists, file minimum size, file freshness, output pattern match, completed-by deadline.
- Wiring into the runtime so `SUCCEEDED` requires process success **and** every required expectation passing; otherwise `OUTCOME_FAILED`.

### Acceptance

- Each expectation result is stored separately with its own evidence.
- A process exiting 0 with a failing required expectation yields `OUTCOME_FAILED`, not `SUCCEEDED`.
- Optional expectations record failure without changing the outcome.
- Evaluator errors yield a recorded evaluation error, not a silent pass.

**Gate:** `product/USER_JOURNEYS.md` Journey 3 passes end to end.

---

## Wave 5 — Scheduling, eligibility, and dependencies

**Goal:** work runs on time, and every non-run is explained.

### Build

- `src/taskcontrol/ports/scheduler.py` — scheduler port with capability metadata (ADR 0007).
- `src/taskcontrol/adapters/schedulers/internal/` — the Phase 1 internal scheduler: durable next-run computation, misfire policy, restart catch-up, no host scheduler writes.
- Cron expression parsing, interval and weekday schedules, IANA time zones, DST-correct next-run preview.
- Run-condition evaluation in deterministic order, returning structured decisions with reason codes.
- Calendar-backed conditions with holidays, exclusions, and provenance.
- Simple dependency eligibility: upstream succeeded, optional freshness window. Not a DAG engine.
- `src/taskcontrol/ports/deployment.py` with a `local` implementation and contract tests, per ADR 0018.

### Acceptance

- Next-run preview is correct across DST spring-forward and fall-back in at least three time zones.
- A skipped execution is a persisted execution with zero attempts, an `ExecutionOutcome.SKIPPED`, and a reason code.
- `SKIPPED` and `BLOCKED` are produced in their correct cases per ADR 0016.
- Restart within the misfire window catches up; outside it, records a misfire.
- The internal scheduler and a manual trigger enter the same runtime path.

**Gate:** parameterised schedule tests over DST and calendar boundaries; Journeys 2, 6, 7, and 8.

---

## Wave 6 — Application services and audit

**Goal:** one orchestration layer that every interface calls.

### Build

- `application/commands/` and `application/queries/` — the complete Phase 1 use-case surface.
- `application/services/` — task authoring, validation, execution control, history queries.
- `domain/governance/` + `adapters/audit/` — immutable audit events for every mutation, manual execution, cancellation, and approval action.
- `ports/notifications.py` with a logging sink implementation.

### Acceptance

- No business rule exists outside `domain/` or `application/`.
- Every mutation produces an audit event with actor, correlation id, and before/after references.
- Audit events are append-only; no code path updates or deletes one.
- Validation returns field-level and cross-field errors with stable codes.

**Gate:** the architecture test extended to assert transport layers contain no branching business logic.

---

## Wave 7 — REST API v1

**Goal:** a documented, versioned public contract.

### Build

`/api/v1` routers for health and readiness, tasks and revisions, profiles, calendars, targets, validation, executions and logs, audit, adapter capabilities. Pydantic request and response schemas, cursor pagination, structured errors with stable codes and correlation ids, OpenAPI metadata, single-administrator authentication boundary with the seam for real identity in Phase 2.

### Acceptance

- Idempotency keys honoured on execution triggers.
- Errors never expose stack traces or internal paths.
- Secret values never appear in any response, including validation previews and error details.
- OpenAPI document generates and validates.
- Every endpoint has an integration test, including its failure paths.

**Gate:** API integration suite green; a schema snapshot test guards accidental contract changes.

---

## Wave 8 — CLI

**Goal:** a first-class client for people, scripts, and CI.

### Build

`taskctl init`, `server`, `task create|list|show|validate|run|archive`, `execution list|show|logs|cancel`, `profile`, `calendar`, `schedule preview`, `adapters list`, `audit list`. Human and `--json` output modes; non-zero exit codes mapped to error taxonomy.

### Acceptance

- The CLI calls application services or the API; it contains no domain logic.
- `--json` output is stable and documented for scripting.
- Exit codes are documented and tested.

**Gate:** CLI smoke tests covering every command's success and primary failure path.

---

## Wave 9 — Web interface

**Goal:** an operational interface, not a decorative dashboard.

### Build

React + TypeScript + Vite under `web/`. Pages: overview, tasks, task detail, task editor (command, schedule, profile, conditions, retry, timeout, expectations), validation results, executions, execution detail with logs and the full decision trail, profiles, calendars, audit, settings and adapter capabilities. Loading, empty, error, and confirmation states throughout.

### Acceptance

- Every displayed value comes from the API. No mocked data, no fabricated metrics.
- The execution detail page answers Journey 13 in order, top to bottom.
- Resolved configuration shows value, source layer, and redaction state.
- The production build succeeds and component tests pass.

**Gate:** Journey 1 completed entirely through the UI.

---

## Wave 10 — Approvals, recovery, and release readiness

**Goal:** the product is operable and installable by someone who is not its author.

### Build

- Approval workflow bound to an immutable revision, per `domain/06`, with `BLOCKED` / `blocked.approval_pending` semantics.
- Restart recovery: reconcile executions left in flight, resolving to `UNKNOWN` or `INFRASTRUCTURE_FAILED` honestly.
- Export and import of task definitions; database backup and restore documentation.
- README walkthrough, troubleshooting, upgrade notes, contribution guidance, `docker-compose.yml` for PostgreSQL.
- One end-to-end test covering define → schedule → run → fail → retry → succeed → inspect.

### Acceptance

- A killed server leaves no permanently in-flight execution after restart.
- A new contributor completes the README walkthrough with no undocumented step.
- Approval decisions are audited and attached to a specific revision.

**Gate:** Phase 1 exit review against `product/PRODUCT_SCOPE.md`'s first-release boundary.

---

## Phase 1 exit criteria

The phase is complete when a user who has never seen the repository can install TaskControl, define a task, schedule it, watch it run, see why it was skipped when it was skipped, inspect logs and every attempt, understand a failure and its retries, cancel a running job, recover from a restart, and manage all of it through the CLI, API, and web interface — without KAE, distributed workers, or enterprise infrastructure.

At that point, reopen `future/DEFERRED_CAPABILITIES.md` and plan Phase 2, whose first capability is scheduler-artefact generation and cron deployment under ADR 0010 and ADR 0018.
