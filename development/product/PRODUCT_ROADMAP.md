# Product Roadmap

- Document level: **0 — Identity**
- Lifecycle state: Canonical
- Sole authority for delivery **phases**. Waves live in `../10_IMPLEMENTATION_BLUEPRINT.md`.
- Related: ADR 0022 (cron owns activation), ADR 0025 (capability and activation model)

## Roadmap principle

Prove the capability lifecycle end to end before expanding into distributed, enterprise, or
ecosystem capability. A release that renders a cron string without proving activation and a
recorded outcome has proven nothing.

**Transports are not roadmap features.** MCP, gRPC, GraphQL, and future surfaces are adapters
over the same application services (ADR 0025). They appear here only as the work of writing an
adapter, sequenced by demand — never as capabilities that change the domain or gate a phase.

## Phase 1 — Cron-backed managed tasks

Deliver an installable standalone product where a user can define a recurring task without
knowing cron, and cron activates it dependably.

- repository, packaging, configuration, logging, migrations, persistence;
- task and immutable revision model, with human-friendly schedule authoring;
- **managed cron artefact rendering, plan, apply, verify, and drift detection**, preserving
  unmanaged crontab content;
- **durable claims** giving overlap protection across separate cron activations (ADR 0023);
- **explicit activation policy** when control state is unreachable (ADR 0024);
- bounded execution services recording attempts, outcomes, and logs;
- drop-in runnable discovery and registration;
- import and adoption of existing cron entries;
- operational knowledge: purpose, owner, source, runbook, criticality;
- CLI and the documented public API foundations;
- restart recovery, documentation, and automated tests.

**Completion proves:** a task defined in TaskControl is activated by cron and recorded by
TaskControl, with the API process stopped during activation.

## Phase 2 — On-demand activation and asynchronous work

- application services accepting an execution request independent of transport;
- REST API for capability management, submission, and status;
- durable request submission returning immediate acceptance;
- cron-woken, bounded queue workers claiming and processing items;
- MCP adapter, once the application services exist — adapter work, not a separate capability;
- retries, idempotency, terminal states, and constrained next-step release;
- practical web interface;
- authentication, authorisation, and stronger audit controls;
- notifications and webhook administration;
- backup, restore, import, export, and upgrade workflows;
- deployment packaging and production runbooks.

**Completion proves:** a remote system submits work without SSH or crontab access, cron
wakes a worker, and the caller can inspect the terminal result.

## Phase 3 — Additional scheduler targets and distributed execution

Only when a real requirement arrives. The architecture keeps the seams open from day one —
capability packages, scheduler adapters, execution adapters, and persistence adapters — but
distributed coordination is not built ahead of need. Coordination designed against guesses is
coordination that will be redesigned.

- systemd timer adapter, then Kubernetes CronJob and Windows Task Scheduler;
- host and host-group inventory, environment and platform classification;
- remote deployment transport and per-host results;
- multi-host drift detection and deployment waves;
- richer approvals, policies, dashboards, and observability;
- hardened plugin and adapter contracts.

Each scheduler adapter manages an **external** scheduler. None reintroduces an internal one.

## Phase 4 — Enterprise and ecosystem

- high availability and horizontal scaling;
- tenancy and federation;
- enterprise identity and policy integrations;
- advanced audit and compliance export;
- integration catalogue and supported adapters;
- KAE and other domain-specific integration packages.

## Prioritisation test

A feature belongs in the near-term roadmap when it materially improves the ability to
define, activate, submit, observe, or govern operational **capabilities** without requiring a
persistent TaskControl scheduler. A transport adapter is sequenced by demand rather than by
phase, because it adds reach without adding domain. Features that primarily serve one external ecosystem, or
that push the product toward a generic workflow engine, belong later or behind an adapter.

## Immediate next step

Realignment waves R0 and R0.1 have reconciled the canonical documentation: cron-backed
activation, then the capability-centred domain model.
Implementation resumes at the wave the blueprint identifies — see
`../10_IMPLEMENTATION_BLUEPRINT.md`. The previous Wave 4 (expectations) is stopped; expected
outcomes return as part of a cron-backed slice rather than as standalone runtime work.
