# Product Roadmap

- Document level: **0 — Identity**
- Lifecycle state: Canonical
- Sole authority for delivery **phases**. Waves live in `../10_IMPLEMENTATION_BLUEPRINT.md`.
- Related: ADR 0022 (cron owns activation)

## Roadmap principle

Prove the cron-backed value chain before expanding into distributed, enterprise, or
ecosystem capability. A release that renders a cron string without proving activation and a
recorded outcome has proven nothing.

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

## Phase 2 — Remote submission and asynchronous work

- REST API for task management and status;
- durable work-item submission returning immediate acceptance;
- cron-woken, bounded queue workers claiming and processing items;
- retries, idempotency, terminal states, and constrained next-step release;
- practical web interface;
- authentication, authorisation, and stronger audit controls;
- notifications and webhook administration;
- backup, restore, import, export, and upgrade workflows;
- deployment packaging and production runbooks.

**Completion proves:** a remote system submits work without SSH or crontab access, cron
wakes a worker, and the caller can inspect the terminal result.

## Phase 3 — Additional scheduler targets and multi-host

Only after cron-backed value is proven:

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
define, activate, submit, observe, or govern operational work **without** requiring a
persistent TaskControl scheduler. Features that primarily serve one external ecosystem, or
that push the product toward a generic workflow engine, belong later or behind an adapter.

## Immediate next step

Realignment wave R0 has reconciled the canonical documentation to the cron-backed direction.
Implementation resumes at the wave the blueprint identifies — see
`../10_IMPLEMENTATION_BLUEPRINT.md`. The previous Wave 4 (expectations) is stopped; expected
outcomes return as part of a cron-backed slice rather than as standalone runtime work.
