# Architecture Overview

- Document level: **1 — Architecture**
- Lifecycle state: Canonical
- Supersedes: `archive/02_ARCHITECTURE.md`, stack sections of `archive/04_TECHNOLOGY_AND_REPOSITORY_STRUCTURE.md`
- Governed by: `../product/PRODUCT_SCOPE.md`, `../decisions/`
- Does not restate: the directory tree (`../engineering/repository/10_REPOSITORY_STRUCTURE.md`), execution vocabulary (ADR 0016), delivery order (`../10_IMPLEMENTATION_BLUEPRINT.md`)

## Architectural style

A modular Python monolith, deployable as one process, with ports-and-adapters boundaries around every external technology: schedulers, executors, persistence, deployment transports, calendars, monitoring, notifications, and secrets (ADR 0002, ADR 0011).

Services are separated only when deployment scale or reliability requires it. Module boundaries must be strong enough that a worker, agent, or service can later be extracted without rewriting the domain.

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

## Runtime flow

One path, entered identically by the internal scheduler, the API, the CLI, and — from Phase 2 — an external scheduler (ADR 0018).

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

### Phase 1 — local-first

```text
Browser / CLI
      |
Python API and application services
      |
SQLite + local artefact store
      |
Internal scheduler
      |
Runtime
      |
Shell / Python / executable
```

TaskControl schedules and runs the work itself. There is one target, `local`, and no host scheduler is written to.

### Phase 2 and later — generation and central management

```text
Web UI -> API -> PostgreSQL
              -> worker / deployment service
              -> local, SSH, or agent transport
              -> host scheduler artefact
              -> the same runtime
```

A generated artefact invokes the same runtime entry point rather than duplicating policy in every script:

```cron
0 7 * * 1-5 /usr/local/bin/taskctl run --deployment-id dep_123
```

Local execution must continue during temporary control-plane unavailability using an approved deployment bundle.

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

An execution left in flight by a process kill must resolve honestly on restart — `UNKNOWN` or `INFRASTRUCTURE_FAILED`, never a silent `FAILED` and never a permanent `RUNNING`.

## Extension constraints

New platform support is added through adapters, never through conditionals spread across domain logic. New run conditions return structured decisions carrying allowed/denied state, reason code, human explanation, and evidence.

Interfaces are introduced at genuine volatility boundaries. An extension point is not removed merely because only one implementation currently exists (engineering law 9).
