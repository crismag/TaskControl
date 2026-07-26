# TaskControl Domain Handbook

## Purpose

This directory is the authoritative software requirements reference for TaskControl's business domain. It defines what each domain concept means, which responsibilities it owns, how it changes over time, and which invariants all implementations must preserve.

The handbook is intentionally independent of FastAPI, SQLAlchemy, React, cron, systemd, Kubernetes, or any other framework. Infrastructure implements these concepts; it does not redefine them.

## Governing principle

> Users define operational intent. TaskControl resolves that intent into safe, observable, deployable execution.

## Reading order

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

When implementation code conflicts with this handbook, the handbook represents intended behaviour unless a newer Architecture Decision Record explicitly supersedes it.

When two handbook files appear to conflict:

1. Prefer the more specific domain file.
2. Preserve the stricter safety or audit requirement.
3. Record the ambiguity in `development/OPEN_QUESTIONS.md`.
4. Do not silently invent new behaviour.

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

The first complete local-first application should implement working vertical slices for:

- Task creation and revision
- Manual and scheduled intent
- Profiles and variables
- Basic calendars and conditions
- Local execution
- Attempts, logs, results, and expected outcomes
- Local target inventory
- Cron deployment preview and guarded application
- Execution history
- Audit history
- Notification hooks

Enterprise concepts may initially be represented by simple implementations, but their domain boundaries must be preserved.