# Deferred Capabilities Register

> **STATUS: FUTURE** — planned capability intentionally outside current
> TaskControl product scope. Not part of Phase 1 implementation.

- Document level: **0 — Identity (future scope)**
- Lifecycle state: Future
- Governed by: `../product/PRODUCT_SCOPE.md`, `../product/PRODUCT_ROADMAP.md`
- Origin: consolidated during the 2026-07-26 canonicalization from documents now in `../archive/`

## Purpose

Every capability removed from the current scope during canonicalization is recorded here with its origin, so that resolving a documentation conflict never destroys a plan. This register is the successor to the capability lists in the retired operating-levels and delivery-roadmap documents.

A capability listed here is **wanted**. It is not deferred because it is a bad idea; it is deferred because Phase 1 must be finishable.

## Phase 2 — Operational maturity

### Scheduler-artefact generation and deployment

The original product thesis, deferred by ADR 0018 and retained in full.

- Managed cron entry and managed-include rendering; systemd timer units.
- Deployment plan preview showing additions, changes, removals, and unchanged artefacts.
- Atomic apply with rollback; idempotent re-apply and removal.
- Preservation of unmanaged crontab content — never a destructive rewrite.
- Ownership and permission checks; configurable sandbox deployment root.
- Content hashes and task/revision identifiers embedded in generated files.
- Stale-plan detection: an applied plan must be the exact approved plan.
- Drift detection for local targets.
- Adapter capability metadata with explicit unsupported-feature validation.

*Origin: `archive/05_DELIVERY_ROADMAP.md` Wave 4; `archive/02_ARCHITECTURE.md`; `archive/06_FULL_APPLICATION_BLUEPRINT.md`; ADR 0010. Architecture remains binding; only implementation is deferred.*

### Crontab import and adoption

- Parse existing crontabs; identify commands, schedules, users, environment declarations.
- Create draft task definitions; flag ambiguous or unsupported constructs.
- Preserve original text; require explicit review before adoption.
- Never overwrite existing entries without a deliberate deployment operation.

*Origin: `archive/01_SCOPE_AND_OPERATING_LEVELS.md` Level 1; `product/USER_JOURNEYS.md` Journey 15.*

### Monitoring contracts and exports

- Generic monitoring contract describing expected observable state.
- Nagios-compatible export; Prometheus metric exposure.
- References to externally owned checks.
- Rule that an external monitor's existence never implies success.

*Origin: `archive/05_DELIVERY_ROADMAP.md` Wave 6; `product/USER_JOURNEYS.md` Journey 11; `domain/07`.*

### Notifications beyond a logging sink

Email, webhook, and chat delivery; per-rule routing; delivery records; suppression windows. Suppression is a delivery concern and never an execution outcome (ADR 0016).

*Origin: `archive/02_ARCHITECTURE.md`; `domain/07`.*

### Templates and task collections

Parameterised templates; ordered and parallel collections with explicit failure behaviour; inherited calendars and switches; environment overrides; bulk planning. Templates must reduce repetition without hiding resolved values.

*Origin: `archive/03_DOMAIN_MODEL.md` TaskCollection; `archive/05_DELIVERY_ROADMAP.md` Wave 6; `product/USER_JOURNEYS.md` Journey 12.*

### Authentication, authorisation, and operational hardening

Real identity providers, role-based access control beyond a single administrator, session management, backup and restore workflows, import/export, upgrade procedures, production runbooks, hardened plugin and adapter contracts.

*Origin: `archive/01_SCOPE_AND_OPERATING_LEVELS.md` Level 2; `product/PRODUCT_ROADMAP.md` Phase 2.*

### Multi-user host operation

Managed execution identities on one host; privilege-aware deployment; private and shared profiles; per-user task collections; delegated administration; log ownership and retention. A deployed instance is identified by deployment scope plus execution identity, never by task name alone.

*Origin: `archive/01_SCOPE_AND_OPERATING_LEVELS.md` Level 2.*

### Durable overlap locking

Phase 1 locking guards a single TaskControl process (ADR 0021). Durable, multi-process
locking is a **Wave 5 requirement**, not an optional improvement, and is listed with its six
deliverables in `../10_IMPLEMENTATION_BLUEPRINT.md`.

Until it ships, TaskControl must not claim overlap protection beyond one process in
documentation, the UI, or an API response. Running two TaskControl processes against one
database in Phase 1 gives no overlap protection.

*Origin: ADR 0021, raised during Wave 3.*

## Phase 3 — Distributed execution

### Remote targets and workers

- Host and host-group inventory; environment and platform classification.
- SSH deployment transport; later a native agent.
- Capability discovery per target; deployment waves with controlled concurrency.
- Per-host results and retry of only the failed hosts.
- Leases, heartbeats, recovery, placement, queues, and resource controls.
- Secure worker identity and transport; signed deployment bundles.

*Origin: `archive/01_SCOPE_AND_OPERATING_LEVELS.md` Level 3; `archive/05_DELIVERY_ROADMAP.md` Wave 7; `domain/05`; ADR 0014; `product/USER_JOURNEYS.md` Journey 4.*

### Additional platform adapters

systemd timers first, then Kubernetes CronJobs and Windows Task Scheduler. Each must pass the shared adapter contract tests. A scheduler that cannot express a condition generates a coarse trigger plus a TaskControl runtime guard rather than dropping the condition.

*Origin: `archive/05_DELIVERY_ROADMAP.md` Wave 8; `product/USER_JOURNEYS.md` Journey 5.*

### Disconnected operation

Deployed work continues while the control plane is unreachable; local history is preserved and synchronised on reconnection. Protocols, identifiers, and bundle formats must not foreclose this.

*Origin: `archive/02_ARCHITECTURE.md`; `product/USER_JOURNEYS.md` Journey 10; ADR 0014.*

### Additional executors

Tcl, HTTP, SQL, and container executors. Tcl support matters for existing engineering estates and is a stated differentiator; it is deferred only because Phase 1 proves the executor port with three adapters.

*Origin: `archive/00_PRODUCT_VISION.md`; `archive/02_ARCHITECTURE.md`; `archive/06_FULL_APPLICATION_BLUEPRINT.md`.*

## Phase 4 — Enterprise and ecosystem

### Enterprise controls

Approval and change workflows beyond Phase 1's single-revision approval; layered organisational configuration; calendar libraries and special operating days; promotion across environments; compliance and audit export; secrets-provider integrations; high availability; retention policies.

*Origin: `archive/01_SCOPE_AND_OPERATING_LEVELS.md` Level 4; `archive/05_DELIVERY_ROADMAP.md` Wave 9.*

### Federation

Independent TaskControl domains under a global view with local control: hierarchical tenancy, metadata federation, policy and template distribution, regional autonomy, aggregated health and audit views, conflict and version management, intermittent-connectivity tolerance.

Federation is explicitly not designed until multiple independent domains exist. The constraint on Phase 1 is only that identifiers, APIs, event records, and ownership boundaries must not make it impossible.

*Origin: `archive/01_SCOPE_AND_OPERATING_LEVELS.md` Level 5; `archive/05_DELIVERY_ROADMAP.md` Wave 10.*

### Integration packages

Supported adapter catalogue; SDKs generated against stable public contracts; domain-specific integration packages including KAE.

A KAE integration package is external-product-specific translation and belongs outside the core, per `product/ECOSYSTEM_BOUNDARIES.md`. TaskControl's **integration surface** — the ports, public API, webhooks, and plugin contracts that such a package would consume — is core product and stays canonical; only KAE's own translation logic would live under `future/kae/`.

*Origin: `product/INTEGRATION_STRATEGY.md`; `product/ECOSYSTEM_BOUNDARIES.md`; `product/PRODUCT_ROADMAP.md` Phase 4.*

## Constraints this register places on Phase 1

Deferral must not foreclose. Phase 1 implementation must preserve:

1. `Target` as a modelled entity, not an assumption of `localhost`.
2. Scheduler, executor, deployment, secret, notification, and monitoring **ports**, each with a real Phase 1 implementation and contract tests.
3. Immutable, content-addressable task revisions that a future plan can reference.
4. A runtime entry point invocable by an external trigger without modification.
5. Tenant and ownership fields absent but not structurally excluded from identifiers and event records.
6. Separable schedule evaluation and eligibility evaluation.
7. Public contracts versioned from the first release.

A Phase 1 change that violates one of these is a defect even though the deferred capability is not yet built.
