> **STATUS: SUPERSEDED** — replaced by `development/product/PRODUCT_SCOPE.md` and `development/product/PRODUCT_ROADMAP.md`.
>
> Retained for historical reasoning. **Do not use for new implementation.**
>
> Superseded: 2026-07-26. Reason: Operating Levels 1-5 were one of three competing delivery partitions. Level 1-2 content is now Phase 1 scope; Levels 2-5 capability lists are preserved in `development/future/DEFERRED_CAPABILITIES.md`. The cross-level invariant model is now `development/domain/`.

---

# Scope and Operating Levels

TaskControl must support progressive operating levels without creating unrelated products or incompatible schemas.

## Level 1 — Personal

One user manages scheduled tasks on one machine.

Capabilities:
- import and inspect a crontab;
- create tasks through CLI, API, or UI;
- generate cron entries and managed runners;
- execute Bash, Python, Tcl, and native commands;
- use retries, timeout, locking, working directories, variables, and logging;
- view execution history;
- preview schedules and run conditions;
- export portable task bundles.

Deployment may use SQLite, local files, and an embedded web/API process.

## Level 2 — Multi-user host

One host contains multiple managed execution identities.

Additional capabilities:
- user and service-account ownership;
- privilege-aware deployment;
- private and shared profiles;
- per-user task collections;
- permissions, delegated administration, and audit;
- safe crontab generation and rollback;
- log ownership and retention rules.

A deployed task instance is uniquely identified by deployment scope plus execution identity, not task name alone.

## Level 3 — Multi-host and multi-platform

A central or workstation-based control plane manages many targets.

Additional capabilities:
- host and host-group inventory;
- environment and platform classification;
- deployment planning and waves;
- SSH or agent-based deployment;
- drift detection;
- cron and systemd adapters initially;
- later Kubernetes CronJob and Windows Task Scheduler adapters;
- platform capability discovery.

The logical task remains platform-neutral. Adapters compile it into target-specific artefacts.

## Level 4 — Enterprise multi-system

Multiple regions, environments, business units, applications, customers, calendars, teams, monitoring systems, and operational controls are managed together.

Additional capabilities:
- role-based access control;
- approval and change workflows;
- layered configuration inheritance;
- calendar libraries and special operating days;
- runtime switches and maintenance controls;
- deployment promotion across environments;
- monitoring and incident integrations;
- compliance and audit reporting;
- secrets-provider integration;
- high availability and backup/restore.

## Level 5 — Federated “multi of multis”

Independent TaskControl domains operate under a global view while retaining local control.

Examples:
- regional control planes;
- separately governed business units;
- managed customers or tenants;
- isolated production networks;
- sovereign or regulated environments.

Capabilities:
- hierarchical tenancy;
- metadata federation;
- policy and template distribution;
- regional autonomy;
- aggregated health and audit views;
- conflict and version management;
- intermittent connectivity tolerance.

Federation is not required for the first implementation, but identifiers, APIs, event records, and ownership boundaries must not make it impossible.

## Cross-level invariant model

At every level, preserve these distinct concepts:

- **Task Definition** — what should be done.
- **Trigger** — when execution should be considered.
- **Run Conditions** — whether execution is allowed now.
- **Execution Profile** — environment and configuration context.
- **Deployment** — where and under which identity the task is installed.
- **Execution Attempt** — one actual evaluation and possible run.
- **Outcome** — success, failure, skipped, blocked, timed out, cancelled, or suppressed.
- **Expectation** — what successful operation should produce or maintain.
- **Monitoring Binding** — how expectations are observed externally.

## Scope-control rule

Features must be implemented at the smallest useful level first. Enterprise concerns should appear initially as interfaces, identifiers, metadata, and extension points rather than premature distributed infrastructure.
