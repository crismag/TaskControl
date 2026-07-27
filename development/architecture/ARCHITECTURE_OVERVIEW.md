# Architecture Overview

- Document level: **1 — Architecture**
- Lifecycle state: Canonical
- Supersedes: `archive/02_ARCHITECTURE.md`, stack sections of `archive/04_TECHNOLOGY_AND_REPOSITORY_STRUCTURE.md`
- Realigned by: ADR 0022 (cron owns activation), ADR 0023 (durable claims), ADR 0024 (activation policy), ADR 0025 (capability and activation model)
- Governed by: `../product/PRODUCT_SCOPE.md`, `../decisions/`
- Does not restate: the directory tree (`../engineering/repository/10_REPOSITORY_STRUCTURE.md`), execution vocabulary (ADR 0016), delivery order (`../10_IMPLEMENTATION_BLUEPRINT.md`)

## The conceptual model

The architecture is layered around the capability, not around the infrastructure serving it
(ADR 0025):

```text
Operational Capability          reusable, versioned, independently deployable definition
        |
Activation Policy               recurring | immediate | deferred        (domain)
        |
Activation Mechanism            cron | CLI | REST | MCP | queue worker  (adapters)
        |
Execution                       bounded, short-lived, records what happened
        |
Observation                     history, audit, metrics, logs
```

Two rules follow, and both are checkable:

1. **Activation never redefines execution.** Whatever activated a request — time arriving, a
   person, an application, an AI system — the execution path is the same one.
2. **The domain is transport-independent.** Every transport is an adapter over the same
   application services. No domain module may branch on activation mechanism; the mechanism
   is recorded as provenance, never consulted.

### Two kinds of activation

| Kind | Meaning | Mechanism |
|---|---|---|
| Recurring | "It is now time to execute this capability." | cron |
| On-demand | "Somebody has requested this work." | CLI, REST, MCP, future transports |

The **queue is infrastructure**, not an activation source: it persists deferred on-demand
requests until a cron-woken worker claims them. Immediate requests bypass it.

## Architectural style

A modular Python codebase with ports-and-adapters boundaries around every external
technology: **scheduler management**, executors, persistence, claims, deployment transports,
calendars, monitoring, notifications, and secrets (ADR 0002, ADR 0011).

The critical shape is the **process model**, not the module layout. TaskControl is not one
long-running application. It is a control plane plus a family of short-lived commands that
cron invokes, and the domain must work identically in both (ADR 0022).

Services are separated only when deployment scale or reliability requires it. Module
boundaries must be strong enough that a worker or service can later be extracted without
rewriting the domain.

## Process model

**No component may implement a recurring in-memory timer or polling loop for activation.**
That is cron's job.

| Shape | Lifetime | Purpose |
|---|---|---|
| Control plane | long-running, **optional** | Web UI and API for management and inspection |
| Cron management command | short-lived | plan, apply, verify, import, adopt |
| Scheduled task wrapper | short-lived | one activation of one managed task |
| Queue worker | short-lived, bounded | claim and process eligible work items |
| Drop-in reconciler | short-lived | discovery, validation, registration |

A deployment may run the API continuously. **Already-installed recurring jobs must not
depend on it.** This is the architecture's defining constraint: if a change would make
scheduled work stop when the control plane stops, the change is wrong.

## Layers

| Layer | Owns | Must not |
| --- | --- | --- |
| Interfaces — CLI, REST API, web client | Translating requests into application commands and results into transport representations | Contain business rules |
| Application services | Use-case orchestration, transactions, authorisation checks, audit emission, port invocation | Import frameworks, sessions, or vendor SDKs |
| Domain engine | Entities, value objects, invariants, state transitions, pure decision policies | Import anything outside the standard library |
| Adapters | Translation to external technology, vendor failure mapping, serialisation | Contain domain policy |
| Infrastructure | Configuration, logging, engine creation, process wiring | Branch on business conditions |

Dependency direction and forbidden edges are normative in `../engineering/repository/11_DEPENDENCY_RULES.md` and enforced by an architecture test.

## Technology baseline

Python 3.12+; FastAPI; Pydantic v2; SQLAlchemy 2 with Alembic; Typer; SQLite by default with PostgreSQL compatibility (ADR 0012); React and TypeScript with Vite for the web client (ADR 0013); pytest; Ruff; mypy; structured logging.

YAML and JSON carry portable declarative definitions, with JSON Schema exported for validation. Task bundles, schemas, and future worker protocols stay language-neutral so a Go or Rust host agent can be introduced later without redesigning the product (ADR 0014). C++ is not part of the stack.

Substitutions require an ADR.

## Activation flow

Authoring and activation are separate paths that meet at the execution services.

**Authoring and deployment** (control plane, or CLI):

1. A user defines a task with a human-friendly schedule.
2. A scheduler-management adapter renders a deterministic managed artefact.
3. A plan shows additions, changes, and removals against installed state.
4. Apply installs the artefact, preserving unmanaged content, and verifies by reading back.

**Activation** (cron, no control plane required):

1. Cron invokes the installed wrapper for one task.
2. The wrapper resolves the task revision and its configuration from locally deployed
   assets where required.
3. It acquires a **durable claim** on the task (ADR 0023). A refused claim is a recorded
   `BLOCKED` execution, not a wait.
4. If control state is unreachable, the task's **activation policy** decides whether to
   proceed with a local journal or refuse (ADR 0024).
5. The execution services run the work under the flow below and the process exits.

### One execution, entered identically

Whether entered by a cron wrapper, a queue worker, or an administrative run-now:

1. A trigger source creates an execution request.
2. The runtime resolves the task revision and its target binding.
3. Configuration layers are merged deterministically, producing a resolution trace (ADR 0009).
4. Run conditions and dependencies are evaluated in a defined order, each returning a structured decision.
5. **An execution attempt record is created even when execution is declined.**
6. If permitted, the runtime acquires the overlap lock and launches the executor with timeout, environment, working-directory, and separated output capture.
7. The process result is classified, then combined with expectation evidence into a terminal outcome (ADR 0016).
8. The retry policy is applied only to eligible outcomes.
9. Logs, events, and audit records are persisted.
10. Notifications are dispatched according to policy.

Steps 3, 4, 7, and 8 are pure functions over stored inputs. Determinism there is what makes decisions explainable.

## Topology

### Phase 1 — cron-backed, single host

```text
Browser / CLI                  (optional, not required for activation)
      |
Python API and application services
      |
SQLite + local artefact store
      ^
      |  records outcomes
      |
Scheduled task wrapper  <---- invoked by ---- cron
      |
Execution services
      |
Shell / Python / executable
```

A managed cron entry invokes the wrapper rather than duplicating policy in every script:

```cron
0 7 * * 1-5 /usr/local/bin/taskctl-run --task daily-settlement-report
```

The exact command name is settled by the CLI design in the cron-backed slice. The property
that matters is that it is short-lived, self-sufficient, and does not require the API.

### Phase 2 and later — remote submission and additional targets

```text
Remote client -> REST API -> durable work queue
                                   ^
                                   | claims and processes
cron ----- wakes -----> bounded queue worker
                                   |
                            Execution services
```

Further scheduler adapters — systemd timers, Kubernetes CronJobs, Windows Task Scheduler —
manage **external** schedulers. None reintroduces an internal one.

## Security boundaries

- Never interpolate untrusted command text into a shell implicitly. Argument arrays by default; `shell=True` requires explicit opt-in in the definition and is recorded in the audit event.
- Separate task authorship, deployment authorisation, and execution identity.
- Secrets are referenced, never embedded in definitions, generated artefacts, logs, previews, API responses, or audit events.
- Record configuration provenance without leaking secret values.
- Validate filesystem paths, ownership, permissions, symlinks, and allowed execution adapters.
- Sign or checksum deployment bundles once multi-host deployment exists.
- No alternate endpoint, CLI path, background job, plugin, or migration may bypass permission checks, audit, redaction, or correlation context.

## Reliability boundaries

Idempotent artefact generation; atomic scheduler-file updates; rollback on deployment failure; locking for overlap control; durable execution records; deterministic profile merge order; a stable status and error taxonomy; UTC persistence with explicit local-timezone display and calendar evaluation.

An execution left in flight by a process kill must resolve honestly on restart — `UNKNOWN` or
`INFRASTRUCTURE_FAILED`, never a silent `FAILED` and never a permanent `RUNNING`. Under
cron-backed activation this matters more, not less: the wrapper process exits every time, so
recovery is driven by **claim lease expiry** (ADR 0023) rather than by a supervising process
noticing.

Overlap protection requires a durable claim. An in-memory lock cannot protect against a
second cron activation, because that activation is a different process.

## Extension constraints

New platform support is added through adapters, never through conditionals spread across
domain logic. A scheduler adapter **manages an external scheduler**; it never becomes one. A
transport adapter translates a request; it never owns an execution path.

### Distribution readiness

The seams that permit multiple machines already exist: capability packages, scheduler
adapters, execution adapters, and persistence adapters. Nothing may assume single-machine
deployment in a way that would require a **domain** change to undo.

The implementation nonetheless stays single-machine until a real requirement arrives.
Distributed coordination built ahead of need is coordination designed against guesses. This
is deliberate evolutionary architecture: ready, not built. New run conditions return structured decisions carrying allowed/denied state, reason code, human explanation, and evidence.

Interfaces are introduced at genuine volatility boundaries. An extension point is not removed merely because only one implementation currently exists (engineering law 9).
