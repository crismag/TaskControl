# Product Scope

- Document level: **0 — Identity**
- Lifecycle state: Canonical
- Sole authority for what is in and out of scope
- Related: ADR 0022 (cron owns activation), ADR 0023 (durable claims), ADR 0024 (activation policy)

## Core responsibility

TaskControl owns the lifecycle, knowledge, and governance of operational work: definition,
human-friendly schedule authoring, cron artefact management, drop-in registration, remote
submission, durable queued work, execution services, observation, and audit.

**It does not own recurring activation.** Cron does (ADR 0022).

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

### Remote operations

- REST API for task management and status;
- asynchronous work-item submission with durable acceptance;
- cron-woken, bounded queue workers;
- web application and CLI access;
- plugin, adapter, event, and webhook extension points.

### Operational support

- configuration, secret references, notifications, and runtime policies;
- import, export, backup, recovery, and migration support appropriate to each release.

## Explicit non-goals

TaskControl does not own:

- **recurring time-based activation** — cron does;
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

The work-item queue is intentionally smaller than a broker:

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

- asynchronous work-item API and cron-woken workers beyond the first bounded slice;
- systemd, Kubernetes, and Windows scheduler adapters;
- remote hosts, distributed worker fleets, and multi-host inventory;
- high availability and clustering;
- complex tenancy and enterprise federation;
- marketplace-style plugins;
- advanced policy engines;
- large-scale event streaming;
- deep KAE-specific adapters.

Deferral must not remove clean extension points, but it must prevent premature complexity.
The register of deferred capability is `../future/DEFERRED_CAPABILITIES.md`.
