# Product Roadmap

## Roadmap principle

Build the first useful TaskControl application before expanding into KAE-specific, distributed, or enterprise capabilities.

## Phase 1 — Functional base application

Deliver an installable standalone product with:

- repository and packaging foundation;
- configuration, logging, migrations, and persistence;
- task and immutable revision domain model;
- manual execution with attempts, outcomes, logs, cancellation, and retry;
- basic scheduling and dependency eligibility;
- REST API and CLI;
- practical web interface;
- local operation, restart recovery, documentation, and automated tests.

Completion proves that a user can operate TaskControl independently for real automated work.

## Phase 2 — Operational maturity

Add capabilities supported by actual usage:

- authentication, authorisation, and stronger audit controls;
- notifications and webhook administration;
- backup, restore, import, export, and upgrade workflows;
- richer approvals, policies, dashboards, and observability;
- hardened plugin and adapter contracts;
- deployment packaging and production runbooks.

## Phase 3 — Distributed execution

Introduce distribution only after local semantics are stable:

- remote workers and capability discovery;
- leases, heartbeats, recovery, and coordination;
- queues, placement, concurrency, and resource controls;
- secure worker identity and transport;
- multi-host operational tooling.

## Phase 4 — Enterprise and ecosystem

Potential later capabilities include:

- high availability and horizontal scaling;
- tenancy and federation;
- enterprise identity and policy integrations;
- advanced audit and compliance export;
- integration catalogue and supported adapters;
- KAE and other domain-specific integration packages.

## Immediate next step

Create the implementation blueprint that converts Phase 1 into ordered development waves with dependencies, file-level outputs, acceptance criteria, tests, and completion gates. After that blueprint, development should move into actual application code rather than further high-level product redefinition.

## Prioritisation test

A proposed feature belongs in the near-term roadmap when it materially improves the ability of the standalone product to define, run, schedule, observe, or govern automated work. Features primarily serving one external ecosystem should be delivered as later integrations unless they expose a genuinely general requirement.