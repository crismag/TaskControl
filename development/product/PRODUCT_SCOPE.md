# Product Scope

- Document level: **0 — Identity**
- Lifecycle state: Canonical
- Sole authority for what is in and out of scope
- Related: ADR 0022 (cron owns activation), ADR 0023 (durable claims), ADR 0024 (activation policy), ADR 0025 (capability and activation model)

## Core responsibility

TaskControl owns the lifecycle, knowledge, and governance of **operational capabilities**:
definition, human-friendly schedule authoring, cron artefact management, package
registration, request submission through any transport, durable queued requests, execution
services, observation, and audit.

**It does not own recurring activation.** Cron does (ADR 0022).

Scope is defined around capabilities and execution requests, never around infrastructure.
Cron, the queue, REST, and MCP are activation mechanisms and adapters (ADR 0025).

## In scope for the base product

### Task management and knowledge

- task definitions and immutable revisions;
- human-friendly schedule authoring, with validated advanced expressions for those who
  prefer them;
- operational knowledge: purpose, owner, source, runbook, criticality, review status;
- drop-in runnable discovery, validation, and registration;
- import and adoption of existing cron entries.

### Cron management

- deterministic managed cron artefact rendering;
- plan, apply, verify-by-read-back, enable, disable, and remove;
- preservation of unmanaged crontab content;
- drift detection between intended and installed state.

### Execution and outcomes

- bounded execution services invoked by cron wrappers, queue workers, or run-now operations;
- attempt records, outcome classification, logs, history, and audit trails;
- retries, timeouts, cancellation, and expected-outcome evaluation;
- durable claims providing overlap protection and work-item claiming (ADR 0023);
- explicit activation policy when control state is unreachable (ADR 0024).

### On-demand activation and transports

- application services accepting an execution request, independent of transport;
- REST API for capability management, submission, and status;
- CLI for immediate and deferred requests;
- MCP and future transports as **adapters over the same application services** — a new
  transport is adapter work, never a domain change, and therefore not a roadmap capability
  in its own right (ADR 0025);
- durable queue persisting deferred requests, claimed by cron-woken bounded workers;
- web application access;
- plugin, adapter, event, and webhook extension points.

### Operational support

- configuration, secret references, notifications, and runtime policies;
- import, export, backup, recovery, and migration support appropriate to each release.

## Explicit non-goals

TaskControl does not own:

- **recurring time-based activation** — cron does;
- transport-specific behaviour in the domain — every transport is an adapter;
- generic DAG or workflow orchestration competing with Airflow, Temporal, Prefect, or
  LangGraph;
- high-throughput message brokering competing with Kafka, RabbitMQ, or Celery;
- container orchestration or CI/CD;
- arbitrary remote shell execution through the ordinary submission API;
- requirements discovery, architecture generation, prompt engineering, model training,
  semantic memory, autonomous research, or source-code generation;
- business-domain-specific logic;
- KAE internals or lifecycle management.

External systems may submit, control, and observe work through public interfaces.

## Deliberate limits on the queue

The queue is **infrastructure, not an activation source**. It persists deferred on-demand
requests until a worker claims them; the activation source is the request that created them.

It is intentionally smaller than a broker:

- cron-woken rather than continuously polling;
- bounded per invocation, so one worker cannot monopolise a host;
- durable and claim-based rather than high-throughput;
- constrained next-step release rather than a general graph language.

If a deployment needs broker throughput, it should use a broker. TaskControl's queue exists
so a remote system can submit operational work without SSH or crontab access.

## First functional release boundary

The first release must prove the cron-backed value chain end to end:

1. installation and local startup;
2. task creation and revision management, without requiring cron syntax;
3. managed cron artefact plan, apply, and verification, preserving unmanaged entries;
4. activation by cron — with the TaskControl API process stopped;
5. execution recorded through the execution services, with attempts, outcomes, and logs;
6. durable claims providing overlap protection across separate activations;
7. an explicit, per-task activation policy when control state is unreachable;
8. persistence and restart recovery;
9. a practical CLI and the documented public API foundations;
10. tests, migrations, configuration, and operational documentation.

A release that renders a cron string without proving activation and recorded outcome has not
met this boundary.

## Deferred capabilities

Future phases unless evidence requires otherwise:

- asynchronous request API and cron-woken workers beyond the first bounded slice;
- MCP and other transport adapters (adapter work, sequenced by demand rather than by phase);
- systemd, Kubernetes, and Windows scheduler adapters;
- **distributed execution across hosts.** The architecture must permit it from day one —
  capability packages, scheduler adapters, execution adapters, and persistence adapters are
  already the seams. The implementation stays single-machine until a real requirement
  arrives, because coordination built before anyone needs it is coordination designed
  against guesses;
- high availability and clustering;
- complex tenancy and enterprise federation;
- marketplace-style plugins;
- advanced policy engines;
- large-scale event streaming;
- deep KAE-specific adapters.

Deferral must not remove clean extension points, but it must prevent premature complexity.
The register of deferred capability is `../future/DEFERRED_CAPABILITIES.md`.
