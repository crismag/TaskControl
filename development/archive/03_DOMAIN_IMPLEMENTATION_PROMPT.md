> **STATUS: SUPERSEDED** — replaced by `development/prompts/IMPLEMENTATION_PROMPT.md` and Wave 1 of `development/10_IMPLEMENTATION_BLUEPRINT.md`.
>
> Retained for historical reasoning. **Do not use for new implementation.**
>
> Superseded: 2026-07-26. Reason: Domain-only scope now expressed as a blueprint wave rather than a separate prompt.

---

# TaskControl Domain Implementation Prompt

You are the principal domain architect and senior Python engineer implementing TaskControl.

## Mission

Translate the authoritative specifications under `development/domain/` into a tested, framework-independent domain and application layer that can support the complete TaskControl application.

This prompt may be used independently for a domain-first implementation or as a focused stage within the full-application generation prompt.

## Required preparation

Before modifying code:

1. Read every file under `development/`.
2. Read `development/domain/README.md` and all numbered domain specifications in order.
3. Inspect the repository and identify existing implementations, conflicts, and incomplete areas.
4. Create or update `development/IMPLEMENTATION_STATUS.md` with a concise baseline.
5. Produce an implementation sequence that delivers vertical slices, not disconnected entity scaffolding.

Do not stop after presenting the plan. Continue into implementation.

## Authoritative rules

- The domain handbook defines intended business meaning.
- A Task is a stable identity; execution-relevant changes create immutable TaskRevisions.
- A Schedule proposes candidate triggers; it does not guarantee execution.
- Run conditions return structured allow, deny, error, or not-applicable decisions.
- A skipped occurrence is not a successful execution and creates no fake attempt.
- An Execution references one immutable TaskRevision and one Target.
- An ExecutionAttempt is one retryable runtime attempt.
- Exit code zero does not prove expected operational outcomes.
- Deployment requires an immutable, reviewable plan before side effects.
- Secret values remain outside persisted configuration, API output, logs, audit, and previews.
- Governance and audit apply through application services, even in simplified local mode.
- Unknown state must be represented honestly.

## Implementation objectives

Implement the following domain groups:

### 1. Shared kernel

- Stable identifiers.
- UTC timestamps and clock port.
- Correlation and causation identifiers.
- Content digest utilities.
- Typed domain errors.
- Result and reason-code types.
- Domain event base types.

### 2. Tasks

- Task aggregate.
- Immutable TaskRevision.
- ActionSpecification.
- TaskCollection.
- Lifecycle transitions.
- Publication and activation validation.
- Revision comparison and digest.

### 3. Scheduling

- Schedule model with explicit IANA time zone.
- Cron and basic interval/one-time schedule support.
- Trigger and idempotency identity.
- Calendar and calendar versions.
- Structured RunCondition tree.
- EligibilityDecision and explanation trace.
- Schedule preview.

### 4. Configuration

- Profile and immutable ProfileVersion.
- Ordered configuration layers.
- Typed variables.
- SecretReference.
- Deterministic resolver.
- Per-key provenance trace.
- Conflict and template-cycle detection.

### 5. Execution

- ExecutionRequest.
- Execution aggregate.
- ExecutionAttempt.
- ProcessResult.
- Retry and timeout policies.
- ExpectedOutcome and OutcomeEvaluation.
- Pure final-result derivation.
- Cancellation and reconciliation commands.

### 6. Deployment

- Target and capabilities.
- InventoryGroup and TargetSelector.
- GeneratedArtefact.
- Immutable DeploymentPlan.
- Deployment and per-target results.
- DriftObservation.
- Local cron adapter contract.

### 7. Governance

- RequestContext and Principal.
- Permission and Role.
- AuthorisationService port.
- Approval request and decision.
- Append-only AuditEvent.

### 8. Integrations

- Adapter descriptors and capability contracts.
- Executor, scheduler, secret-provider, notification, monitoring, inventory, and artefact-store ports.
- NotificationRule and NotificationDelivery.
- Plugin manifest and lifecycle.

## Architecture constraints

- Domain modules must not import FastAPI, SQLAlchemy, Typer, React, or concrete adapters.
- API and CLI schemas must not be reused as domain entities.
- ORM models may be separate mappings or persistence models.
- Application services coordinate repositories and ports.
- External side effects happen through ports and are recorded/reconciled.
- Avoid a generic service or repository that erases domain language.
- Prefer composition and explicit state machines.
- Use Python typing thoroughly.
- Use dataclasses, attrs, or carefully designed Pydantic-free domain classes according to repository standards.

## Persistence implementation

Create SQLAlchemy mappings and Alembic migrations for the implemented aggregates.

At minimum persist:

- Tasks and revisions.
- Schedules and calendars.
- Conditions.
- Profiles and versions.
- Secret references.
- Targets and capabilities.
- Triggers and eligibility decisions.
- Executions, attempts, state transitions, and outcome evaluations.
- Deployment plans, deployments, and drift observations.
- Principals, roles, permissions, approvals, and audit events.
- Notification rules and deliveries.

Use database constraints for uniqueness and immutable-reference integrity where practical.

## Required first vertical slices

Implement these in order and keep each working:

### Slice A — Task definition

Create a Task, create a revision, publish it, activate it, retrieve it, and compare revision history.

### Slice B — Eligibility

Attach a schedule, calendar, and run condition. Preview future occurrences and explain an allowed and skipped occurrence.

### Slice C — Configuration

Resolve layered profiles and show the origin of each effective value while retaining only secret references.

### Slice D — Local execution

Request a manual run, execute a safe local program, capture logs, persist an attempt, and derive final result.

### Slice E — Expected outcomes

Run a process that exits zero but fails a required file expectation, producing `OutcomeFailed`.

### Slice F — Deployment plan

Render a managed local cron artefact, show a diff, store the plan, and apply only through an explicit deployment command.

### Slice G — Governance

Reject an unauthorised deployment, create an approval when configured, and write correlated audit events.

## Testing requirements

Create:

- Unit tests for every legal and illegal lifecycle transition.
- Property-based tests for configuration precedence, trigger idempotency, and schedule/time-zone edge cases where feasible.
- Persistence integration tests for constraints and optimistic concurrency.
- Adapter contract tests.
- Application-service tests for authorisation and audit.
- End-to-end tests for all required vertical slices.

Include explicit tests for:

- Published revision immutability.
- Duplicate scheduled trigger suppression.
- DST gap and overlap policy.
- Calendar skip versus condition error.
- Secret redaction.
- Overlap prevention race.
- Retryable versus non-retryable result classification.
- Exit zero with failed expected outcome.
- Stale deployment plan rejection.
- Partial deployment representation.
- Approval digest mismatch.
- Unknown state reconciliation.

## Documentation outputs

Update or create:

- Root README quick start.
- Architecture overview.
- Domain model diagram using Mermaid.
- API and CLI examples for the vertical slices.
- `development/IMPLEMENTATION_STATUS.md`.
- ADRs for any material deviation from documented architecture.

## Completion behaviour

Do not claim completion because classes, tables, or endpoints exist. Completion requires working behaviour and tests.

When blocked by environment limits:

1. Complete everything that can be completed locally.
2. Implement a deterministic fake or contract test only where an external system is unavailable.
3. Clearly mark the boundary between implemented production behaviour and simulated test behaviour.
4. Record the exact remaining tasks and commands in `development/IMPLEMENTATION_STATUS.md`.

## Final report

At the end, provide:

- Implemented domain groups.
- Vertical slices demonstrated.
- Tests run and results.
- Migrations created.
- Known limitations.
- Security-sensitive decisions.
- Deviations and ADR references.
- Exact next recommended implementation step.

Begin by reading the repository and authoritative context, then proceed through implementation without stopping after analysis or scaffolding.
