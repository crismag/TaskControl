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

**Repository state: Waves 0–3 complete under the previous internal-scheduler direction, and
retained. The product direction changed on 2026-07-27: cron now owns recurring activation
(ADR 0022). The completed work is repositioned as supporting execution services, not
discarded.**

**Next action: R2 — Managed cron artefact vertical slice.**

| Wave | Name | Status |
| --- | --- | --- |
| 0 | Foundation and quality gates | complete (previous direction) — retained |
| 1 | Domain core | complete (previous direction) — retained |
| 2 | Persistence and migrations | complete (previous direction) — retained |
| 3 | Runtime and executors | complete (previous direction) — retained, repositioned |
| R0 | Canonical product and architecture reconciliation | **complete** (2026-07-27) |
| R1 | Wave 3 compatibility review and terminology cleanup | **complete** (2026-07-27) |
| R2 | Managed cron artefact vertical slice | not started |
| R3 | Drop-in discovery and registration | not started |
| R4 | Operational knowledge, import, adoption, and drift | not started |
| R5 | Asynchronous work-item API and cron-woken worker | not started |

### The old Wave 4 is stopped

The previous Wave 4 (expectations and outcome evaluation) is **cancelled as a standalone
wave**. Expected outcomes remain a real product capability and return inside a cron-backed
slice, where a failing expectation can be observed on a task cron actually activated. Waves
5–10 of the previous sequence are superseded by R2–R5 and the phases in
`product/PRODUCT_ROADMAP.md`.

Nothing in Waves 0–3 is rewritten to pretend it always targeted this architecture. It did
not. It was built correctly under ADR 0018, which ADR 0022 supersedes.

## Scope boundary for Phase 1

Per ADR 0022, **cron owns recurring activation**. TaskControl renders, installs, and verifies
managed cron artefacts, then records what happens.

**In Phase 1:** task definitions and immutable revisions; human-friendly schedule authoring;
managed cron artefact plan/apply/verify/drift, preserving unmanaged entries; import and
adoption of existing cron entries; drop-in discovery and registration; durable claims
(ADR 0023); explicit activation policy under degraded control state (ADR 0024); bounded
execution services recording attempts, outcomes, and logs; operational knowledge; CLI and
public API foundations; restart recovery.

**Not in Phase 1:** an internal scheduler of any kind; distributed execution across hosts —
the seams stay open, the coordination is not built (ADR 0025); scheduler adapters beyond
cron; a generic DAG language; broker-scale queueing; RBAC beyond a single administrator;
notifications beyond a logging sink.

Transport adapters — MCP, gRPC, GraphQL — are not waves. They are adapter work over the
application services R5 establishes, sequenced by demand.

**No component may run a recurring timer or polling loop for activation.** If a wave appears
to need one, the design is wrong.

## Rules that apply to every wave

1. The repository is runnable and green at the end of every wave. `make check` passes.
2. Tests are written during the wave, not after it.
3. A wave does not implement a later wave's capability. If you need it, stub the port and
   record it.
4. Every wave updates this document's status table and any affected Level 0/1 document.
5. Deferred work goes in `future/DEFERRED_CAPABILITIES.md` or `OPEN_QUESTIONS.md`, never in
   scattered `TODO` comments.
6. No mock data behind a real interface.
7. **Nothing may reintroduce an always-on activation process, under any name.**

---

## Realignment waves

### R0 — Canonical product and architecture reconciliation — **complete**

Documentation only. Established cron-backed identity across Level 0 and Level 1, added
ADRs 0022, 0023, and 0024, marked ADRs 0018 and 0021 superseded without erasing them,
stopped the old Wave 4, and reconciled the index and audit.

**Gate:** one product identity in the repository; no active document describes an internal
scheduler as the activation engine.

---

### R1 — Wave 3 compatibility review and terminology cleanup

**Goal:** know exactly which of the existing code works under cron-backed activation, on
evidence rather than assumption.

#### Build

A written review — not a refactor — answering, with references to source:

- whether execution services are callable from a short-lived process that exits;
- whether anything assumes one persistent in-memory scheduler;
- whether persistence and claims work across independent process invocations;
- whether attempts can be associated with a cron activation and later with a work item;
- whether failure to reach the control plane blocks local execution, and where that decision
  currently lives;
- whether configuration can resolve entirely from locally deployed assets;
- which names encode the scheduler-first model and what they should become.

The R0 reconciliation swept the repository and found these source locations still asserting
the superseded direction. They were deliberately **not** edited, because R0 was
documentation-only and naming is R1's job:

| Location | What it now gets wrong |
|---|---|
| `src/taskcontrol/__init__.py` | Package docstring says TaskControl schedules work "itself through an internal scheduler" and "does not write to any host scheduler configuration" — both now inverted |
| `src/taskcontrol/domain/execution/execution.py` | `TriggerSource.SCHEDULE` is documented as "the internal scheduler reached an occurrence"; it now means cron activated a managed artefact |
| `src/taskcontrol/application/runtime/service.py` | Module docstring names "the internal scheduler" as a future caller |
| `src/taskcontrol/application/runtime/__init__.py` | Same |

Also for R1: `docs/DEVELOPMENT.md` and the domain handbook still present `taskctl run` as an
ordinary workflow. It remains valid as an administrative and validation command, but it is no
longer the scheduled-job path and should not read as though it were.

Then the minimum code changes the review proves necessary:

- rename what misleads;
- mark `ProcessLocalOverlapLock` as a test double, not production overlap protection
  (ADR 0023);
- add the `activation_policy` field to the revision schema with the strict default
  (ADR 0024).

#### Acceptance

- The review is committed and names specific modules.
- No production path constructs `ProcessLocalOverlapLock`.
- `activation_policy` exists, defaults to `require_control_state`, and round-trips.
- No behaviour change beyond those two, and no Wave 3 capability is deleted.

**Gate:** the existing suite still passes; the review states plainly what is reusable and
what is not.

#### Outcome

The review is at `reviews/R1_WAVE3_COMPATIBILITY.md`. Every claim in it was produced by
running the code, not by reading it.

**Verdict: Wave 3 is substantially reusable.** Execution services, outcome vocabulary,
attempt persistence, retry classification, and the terminal-state guarantee all work
unmodified from short-lived processes. Nothing assumes a persistent scheduler — the only two
loops are per-execution.

Three findings change R2's scope:

1. **The overlap lock protects nothing, measured.** Two concurrent activations of a task with
   `OverlapPolicy.FORBID` both ran to completion. `ProcessLocalOverlapLock` is now a test
   double; production wires `NoOverlapProtection`, which grants and logs that it granted,
   because an honest absence beats a lock that looks real in a code review.
2. **The runtime reads its revision from the database before it can execute**, so ADR 0024's
   availability-first policy is currently unimplementable. A cron wrapper must resolve its
   revision from locally deployed assets.
3. **Persistence failures leak 43 lines of traceback** including filesystem paths, violating
   the API and database standards. The exit code is correct at 1, so cron sees the failure.

Changes made: the five misleading docstrings, the lock demotion, and `activation_policy` on
the revision (schema 1.1, defaulting to `require_control_state`). No Wave 3 capability was
deleted.

**Deferred deliberately:** renaming `Task` to `Capability`. The concepts are right and only
the labels lag; renaming now would touch every module, the storage schema, and the published
JSON Schema, and would collide with R2 adding fields to the same classes. Revisit after R2.

---

### R2 — Managed cron artefact vertical slice

**Goal:** the complete user value chain — define without cron syntax, apply, let cron
activate, inspect the outcome.

#### Build

- `ports/scheduler_management.py` — plan, apply, verify, remove against an external
  scheduler.
- `adapters/schedulers/cron/` — deterministic rendering, managed-block identity, crontab
  read, write, and read-back verification.
- **Durable claim capability** (ADR 0023): one primitive, with the scheduled-overlap policy.
  This wave delivers it, because cron-backed activation cannot be called overlap-safe
  without it — R1 measured two concurrent activations both running.
- **Locally resolvable revisions** (R1 Finding 2). A cron wrapper must learn what to run, and
  its own activation policy, from a locally deployed artefact — the task package or a
  snapshot written at apply time. The database records; it does not decide. Without this,
  ADR 0024's availability-first mode cannot be implemented at all.
- **Persistence errors wrapped at the boundary** (R1 Finding 3). Translate SQLAlchemy
  failures into the error taxonomy so an operator with a down database sees an explanation,
  not a traceback with filesystem paths.
- Activation policy enforcement (ADR 0024), including the local journal path and its
  reconciliation.
- A short-lived wrapper command that cron invokes.
- `plan`, `apply`, `verify`, `status`, `disable`, `enable` operations.

#### Acceptance

- Human-friendly schedule renders to the expected cron expression, deterministically.
- Unmanaged crontab entries survive apply byte for byte.
- Re-apply is idempotent; schedule update produces a correct plan and apply.
- Read-back verification detects a mismatch; ambiguous managed-block identity fails closed.
- A failed apply rolls back.
- **A task activates and records an outcome with the API process stopped.**
- Two concurrent activations of one task: exactly one runs, the other is `BLOCKED` with
  `blocked.overlap_lock_held` — proven by a multi-**process** test.
- Both activation policies behave as ADR 0024 specifies with persistence stopped, and a
  journalled run reconciles into exactly one execution record.

**Gate:** an integration test that installs a managed entry into a temporary crontab, waits
for or safely simulates activation, and asserts the recorded outcome — with no TaskControl
service running.

---

### R3 — Drop-in discovery and registration

**Goal:** a runnable placed in an approved directory becomes a managed task without anyone
editing a crontab.

#### Build

Directory scanning, package validation, content identity, registration and update proposals,
quarantine for invalid packages, and a reconciler invocable by cron.

#### Acceptance

- A valid package is discovered, validated, and registered.
- An invalid or incomplete package is quarantined and reported, never silently activated.
- Permissions, ownership, and path safety are validated before anything is trusted.
- Re-running discovery is idempotent.
- A removed package is detected and its managed entry handled explicitly, not orphaned.

**Gate:** discovery runs as a short-lived cron-invoked command against a temporary directory
tree.

---

### R4 — Operational knowledge, import, adoption, and drift

**Goal:** an operator can point TaskControl at an existing estate and understand it.

#### Build

Ownership, purpose, source, runbook, criticality, and review status on tasks. Import of
existing user and system cron sources, classifying managed, unmanaged, duplicate,
conflicting, and broken entries. Adoption without rewriting. Drift detection between
intended and installed state.

#### Acceptance

- Import identifies managed and unmanaged entries and never modifies anything during import.
- An entry can be adopted without changing the installed line.
- Drift is detected and explained: what differs, and which side changed.
- A missing runnable or directory is reported rather than discovered at activation.

**Gate:** import a realistic crontab fixture and produce an accurate, explainable inventory.

---

### R5 — On-demand activation: request API and cron-woken worker

**Goal:** a remote system submits durable work without SSH, filesystem access, or crontab
edits — through an application service that any transport can call.

The application service comes first and the REST adapter second, because MCP and any future
transport must plug into the same service rather than grow a parallel path (ADR 0025). Adding
MCP afterwards should be adapter work with no domain change; if it is not, this wave got the
boundary wrong.

#### Build

An application service accepting an execution request with its provenance, then
`POST /api/v1/work-items` over it, accepting a **registered task type**, payload, idempotency
key, and optional not-before time, returning immediate durable acceptance. Persistent work-item
state. A bounded, cron-woken worker that claims items using the same durable claim primitive
(ADR 0023), processes them, records attempts, and moves them to terminal or retry-wait.
Status queries.

#### Acceptance

- Submission returns an identifier and accepted status without waiting for execution.
- A duplicate idempotency key returns the original item; the work runs once.
- Two concurrently woken workers never process one item twice.
- A worker killed mid-item releases its claim by lease expiry, and the item becomes eligible
  again.
- One invocation processes a bounded number of items and exits.
- The API refuses arbitrary shell commands.
- No domain module branches on activation mechanism; the mechanism is recorded as provenance.
- A second transport could be added by writing an adapter alone — demonstrated by a test that
  drives the same application service directly, without HTTP.

**Gate:** submit through the API with no worker running, wake a worker, and observe the
terminal result — end to end.

---

## Retained waves, previous direction

The four waves below were completed under ADR 0018 and are retained. Their outcomes are
recorded honestly, including the assumptions that no longer hold.

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

## Phase 1 exit criteria

The phase is complete when an operator can install TaskControl, define a recurring task
without writing a cron expression, apply the managed cron entry, watch cron activate it with
the TaskControl service stopped, see the outcome recorded with attempts and logs, adopt an
existing crontab into management, and trust that two activations of one task will not
overlap.

### The recognition test

Phase 1 is not complete on capability alone. It must also pass:

> Can a production engineer who has never seen TaskControl immediately recognise it as a
> platform that automates the work they currently perform manually?

Concretely, that requires at least:

- a README whose first demonstration is a **before-and-after crontab**, not a feature list;
- worked examples drawn from real operational work — a backup, a market-close job, a report
  — rather than from the data model;
- a quickstart where the first command produces something an engineer recognises, in
  minutes, without reading a design document;
- failure output that reads like an incident note rather than a status enum.

A release that satisfies every functional criterion above and fails this one has built the
right machinery behind the wrong front door.

At that point, reopen `product/PRODUCT_ROADMAP.md` and plan Phase 2, whose first capability
is remote asynchronous submission.
