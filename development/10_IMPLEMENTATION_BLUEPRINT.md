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

**Repository state: Waves 0–3 complete. TaskControl runs real work, classifies the result
honestly, records every attempt, and always finishes an execution in a terminal persisted
state. Expectations are not yet evaluated, and scheduling is not yet automatic.**

**Next action: Wave 4 — Expectations and outcome evaluation.**

| Wave | Name | Status |
| --- | --- | --- |
| 0 | Foundation and quality gates | **complete** (2026-07-26) |
| 1 | Domain core | **complete** (2026-07-27) |
| 2 | Persistence and migrations | **complete** (2026-07-27) |
| 3 | Runtime and executors | **complete** (2026-07-27) |
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

Verified: `make check` green; `taskctl version` and `taskctl health` exit 0;
`GET /api/v1/health` and `/api/v1/ready` return 200; invalid configuration exits 78; the
architecture test was confirmed to fail on a deliberately planted forbidden import and
pass once removed.

### Follow-up: defects found by running the application

Running the server — as opposed to running the suite — exposed two defects that the tests
could not see, since both concerned what happens under a real ASGI server. Fixed in a
follow-up commit; 96 tests, 95% coverage.

1. **`api_host` and `api_port` did nothing.** They were validated, reported by
   `taskctl health`, and logged at startup, but the bind address came from uvicorn's own
   command line, so the reported configuration could disagree with reality. Added
   `taskctl server`, which binds from settings; `infrastructure/server.py` owns process
   startup.
2. **Uvicorn's logs bypassed structured logging entirely.** `uvicorn` and `uvicorn.access`
   ship with `propagate = False` and their own handlers, so the process emitted JSON for
   application events and plain text for everything the server said, with no correlation
   identifier on any request. Added `uvicorn_log_config`, and moved the access log into
   the request middleware where correlation context is bound.

Both are worth noting for later waves: **a Wave's acceptance criteria should include
running the thing, not only testing it.** Waves 7 and 9 in particular assert behaviour that
only appears under a real server or browser.

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

### Outcome

Delivered in five slices: `common` (identifiers and value objects), `execution` (the ADR
0016 vocabulary), `policies` (classification and retry), `tasks` (Task, TaskRevision,
ActionSpecification), `configuration` (layers and resolution), `scheduling` (schedules,
calendars, conditions), and the serialization adapter with examples and JSON Schema.

Deviations and decisions worth carrying forward:

1. **Serialization is an adapter, not domain code.** `domain/` may import only the
   standard library, so PyYAML cannot live there. Domain types expose
   `to_primitive`/`from_primitive`; `adapters/serialization/` owns the file format. The
   constraint improved the design — the wire format is now entirely replaceable.
2. **The JSON Schema is hand-maintained, not reflected** from the dataclasses. Generating
   it would publish every internal rename as a breaking contract change. Enum members are
   read from the domain enums, and a test asserts the exported file matches the code, so
   it cannot drift silently.
3. **`UUIDv7` is implemented here** — `uuid.uuid7` arrives in Python 3.14. Identifiers sort
   by creation time, which Wave 2 will rely on for index locality.
4. **Two bugs were found by tests rather than review**: `astimezone` on a datetime already
   in the target zone is a no-op, so the DST nonexistent-time check never fired; and a
   `Protocol` declaring a mutable attribute is not satisfied by a frozen dataclass field.

Verified: `make check` green; 578 tests; 94% coverage; both examples round-trip
byte-identically; both validate against the exported schema; `domain/` imports nothing
outside the standard library, enforced by the Wave 0 architecture test.

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

### Outcome

Delivered as specified, with one placement change and two decisions worth carrying:

1. **The unit of work lives in `adapters/persistence/`, not `infrastructure/`** as this
   document originally said. It constructs SQLAlchemy repositories and owns a SQLAlchemy
   session, which makes it a persistence concern rather than a neutral process-level one.
   The architecture test caught the import the moment it existed.
2. **Revision content is stored as a JSON document**, not normalised columns. Normalising
   would mean a migration every time an executor option is added, and would put the
   immutability guarantee at the mercy of a schema change. The digest is stored beside it
   so integrity is checkable without parsing.
3. **Timestamps are stored UTC-naive.** SQLite cannot hold an offset and would round-trip
   an aware value into a lie. Mappers attach UTC on the way out; a test asserts no naive
   datetime reaches the domain.

Also beyond the listed scope: readiness now reports database reachability and schema
currency, because a process serving against an out-of-date schema fails confusingly.

Verified: `make check` green; 633 tests, 34 PostgreSQL tests skipping with an actionable
message; `taskctl init` creates and upgrades idempotently; a task written by one process is
read back with a verifying digest by another; `/api/v1/ready` returns 503 with
`"Run 'taskctl init'"` before initialisation and 200 after.

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

### Outcome

Delivered as specified, with two ADRs raised during the wave.

**ADR 0020 — reason codes distinguish termination causes.** A timeout, a cancellation, and
an external kill are the same event at the operating-system level. The outcome enum is
unchanged; the reason-code vocabulary now covers `TIMED_OUT`, `CANCELLED`, and `FAILED`, and
the cause is recorded when termination is *requested* rather than inferred from the signal.

**ADR 0021 — overlap locking is process-local until Wave 5.** See the Wave 5 requirement
below.

Two decisions worth carrying:

1. **Secret references are refused, not resolved.** A revision needing a secret fails with
   `INFRASTRUCTURE_FAILED` and an explanation, because the secrets adapter does not exist
   yet and the alternatives — inventing a value or silently dropping the binding — are both
   worse than refusing.
2. **The environment is replaced, not inherited.** A task sees exactly what it resolved
   plus a minimal base, so it cannot read whatever secrets happen to be in the TaskControl
   process. Tested with a canary.

**The expectations seam stays dormant.** `SUCCEEDED` means the process succeeded, and
`OUTCOME_FAILED` is unreachable until Wave 4 supplies real evidence. Tests assert that
rather than fabricating evidence to exercise the path.

A real defect was found by the suite: the executor leaked subprocess pipes, which
`filterwarnings = ["error"]` surfaced as a failure. A long-running TaskControl process
would eventually exhaust its file descriptors.

Verified: `make check` green; 693 tests, 90% coverage; success, non-zero exit, launch
failure, timeout, SIGTERM-ignored-then-SIGKILL, and lock contention each produce the correct
outcome and reason code against real subprocesses; retries persist separate attempts; no
execution is left unfinished across every kind of ending.

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
- **Durable overlap locking (required, not optional).** ADR 0021 defers it to this wave and
  states that TaskControl may not claim overlap protection beyond one process until it
  exists. It must deliver all six of:
  1. a row-level claim durable across process restart;
  2. an explicit owner identity per claim;
  3. a lease with an expiry, so a dead owner does not block a task forever;
  4. stale-lock recovery reconciling claims whose owner cannot be observed;
  5. multi-**process** contention tests, not merely multi-thread ones;
  6. documented behaviour when the lock store is unavailable — `CONDITION_ERROR` or
     `INFRASTRUCTURE_FAILED`, never an assumed acquisition.
  The `OverlapLock` port and its contract tests already exist; this wave adds an
  implementation behind them and must pass the same tests unchanged.

### Acceptance

- Next-run preview is correct across DST spring-forward and fall-back in at least three time zones.
- A skipped execution is a persisted execution with zero attempts, an `ExecutionOutcome.SKIPPED`, and a reason code.
- `SKIPPED` and `BLOCKED` are produced in their correct cases per ADR 0016.
- Restart within the misfire window catches up; outside it, records a misfire.
- The internal scheduler and a manual trigger enter the same runtime path.
- Overlap protection holds across two TaskControl processes sharing one database, proven by
  a multi-process test. Until this passes, the process-local limitation of ADR 0021 stands
  and must not be contradicted in documentation or the UI.

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
