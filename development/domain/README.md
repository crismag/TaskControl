# TaskControl Domain Handbook

- Document level: **1 — Architecture**
- Lifecycle state: Canonical

## Purpose

This directory is the authoritative software requirements reference for TaskControl's business domain. It defines what each domain concept means, which responsibilities it owns, how it changes over time, and which invariants all implementations must preserve.

The handbook is intentionally independent of FastAPI, SQLAlchemy, React, cron, systemd, Kubernetes, or any other framework. Infrastructure implements these concepts; it does not redefine them.

## Governing principle

> Users define operational intent. TaskControl resolves that intent into safe, observable, deployable execution.

## Terminology after the cron-backed realignment

ADR 0022 changed what activates recurring work. Four terms in this handbook must be read
with the corrected meanings below. The concepts survive; the assumptions attached to them do
not.

| Term | Corrected meaning |
|---|---|
| **Schedule** | Desired activation intent, rendered and deployed through a scheduler-**management** adapter. It is not evidence that TaskControl runs a scheduler. |
| **Trigger** | An activation event arriving from cron, a queue worker, or an explicit run-now request. TaskControl does not generate recurring triggers itself. |
| **Execution** | One managed attempt to perform work, in a short-lived process. It may be initiated by cron, a worker, or an administrator. |
| **Runtime** | Bounded execution services — locking, timeout, capture, classification, recording. It does not mean an always-on daemon. |
| **Dependency** | Operational eligibility and constrained next-step release. It is not a general DAG language, and must not grow into one without an explicit product decision. |
| **Claim / lease** | Durable, time-bounded ownership of a subject. One capability serves both scheduled-overlap prevention and work-item claiming (ADR 0023). |
| **Operational Capability** | The reusable, versioned, independently deployable definition of something the organisation can do. The primary domain concept (ADR 0025). Currently modelled in code as `Task` plus `TaskRevision`. |
| **Execution Request** | One request that a capability be performed, carrying its provenance — which mechanism activated it, and who asked. Currently `RunRequest`. |
| **Execution Instance** | One recorded attempt to perform a capability. Currently `Execution`. |
| **Activation policy** | How a capability becomes active: recurring, immediate, or deferred. A domain concept, held in the definition. |
| **Activation mechanism** | What caused this particular request: cron, CLI, REST, MCP, or a queue worker. An adapter concern, recorded as provenance and **never** branched on in the domain. |
| **Queue** | Infrastructure persisting deferred on-demand requests until a worker claims them. Not an activation source. |

Where a handbook file still reads as though TaskControl owns activation, this table governs
and the file is scheduled for correction in blueprint wave R1.

The capability vocabulary post-dates the implementation. R1 decides, on evidence, whether the
code is renamed to match or whether the mapping above is sufficient. The concepts already
exist either way.

## Order within this handbook

1. `00_DOMAIN_LANGUAGE_AND_BOUNDARIES.md`
2. `01_TASKS_REVISIONS_AND_COLLECTIONS.md`
3. `02_SCHEDULES_TRIGGERS_CALENDARS_AND_CONDITIONS.md`
4. `03_PROFILES_CONFIGURATION_AND_SECRETS.md`
5. `04_EXECUTIONS_ATTEMPTS_RESULTS_AND_EXPECTATIONS.md`
6. `05_TARGETS_INVENTORY_DEPLOYMENTS_AND_DRIFT.md`
7. `06_IDENTITIES_ROLES_APPROVALS_AND_AUDIT.md`
8. `07_NOTIFICATIONS_INTEGRATIONS_AND_PLUGINS.md`
9. `08_LIFECYCLES_INVARIANTS_AND_FAILURE_SEMANTICS.md`
10. `09_DOMAIN_IMPLEMENTATION_CONTRACT.md`

## Domain groups

### Definition domain

- Task
- Task revision
- Task collection
- Command or action specification
- Execution policy

### Scheduling domain

- Schedule
- Trigger
- Calendar
- Run condition
- Time window

### Configuration domain

- Profile
- Variable
- Secret reference
- Configuration layer
- Resolution trace

### Execution domain

- Execution request
- Execution
- Attempt
- Result
- Expected outcome
- Evidence

### Deployment domain

- Target
- Host
- Platform
- Environment
- Inventory group
- Deployment plan
- Deployment
- Generated artefact
- Drift observation

### Governance domain

- User
- Service identity
- Role
- Permission
- Approval
- Audit event

### Integration domain

- Notification rule
- Notification delivery
- Monitoring integration
- Scheduler adapter
- Executor adapter
- Plugin

## Non-collapsing rule

The following concepts must remain separate even when an early implementation stores or displays them together:

- Task definition and task revision
- Schedule and trigger occurrence
- Execution and execution attempt
- Process exit result and operational expected outcome
- Deployment plan and deployment execution
- Target definition and observed target state
- Profile definition and resolved runtime configuration
- Secret reference and secret value
- Audit event and ordinary application log

Collapsing these concepts produces hidden state, weak auditability, and poor upgrade paths.

## Specification template

Each domain specification describes:

- Purpose
- Responsibilities
- Required attributes
- Relationships
- Lifecycle
- Validation rules
- Commands and queries
- Persistence guidance
- API representation
- UI representation
- Security and audit considerations
- Failure behaviour
- Future extensions

## Authority and conflict resolution

This handbook does not rank itself against other packages. Precedence, the reading order, and the single-authority map live in `../00_CONTEXT_INDEX.md` (ADR 0017).

Within this handbook, when two files appear to conflict:

1. Prefer the more specific domain file.
2. Preserve the stricter safety or audit requirement.
3. Record the ambiguity in `../OPEN_QUESTIONS.md`.
4. Do not silently invent new behaviour, and do not resolve it by writing a third file.

## Implementation guidance for coding agents

Before modifying a domain object, read every specification that names it. Changes often cross boundaries. For example, editing Task activation behaviour requires reviewing task lifecycle, schedule eligibility, deployment reconciliation, execution creation, and audit requirements.

Coding agents must:

- Place business rules in the domain or application-service layer.
- Keep API handlers, CLI commands, and UI components thin.
- Use explicit state transitions rather than arbitrary status assignment.
- Record domain-significant changes as audit events.
- Preserve revision history.
- Use stable identifiers.
- Keep public schemas versionable.
- Avoid hard-coding one scheduler or operating system into the domain.

## Initial product scope

This handbook defines the domain in full, across all phases. **What is built now is decided by `../10_IMPLEMENTATION_BLUEPRINT.md`, not here.**

Concepts specified in this handbook whose implementation is deferred — target inventory, deployment plans, drift, generated artefacts, notification delivery beyond a logging sink — remain binding as *domain definitions* while their implementation waits (ADR 0018). Their boundaries must be preserved by Phase 1 code even though Phase 1 does not build them. See `../future/DEFERRED_CAPABILITIES.md` for the register and the constraints it places on Phase 1.

Enterprise concepts may initially be represented by simple implementations, but their domain boundaries must be preserved.
