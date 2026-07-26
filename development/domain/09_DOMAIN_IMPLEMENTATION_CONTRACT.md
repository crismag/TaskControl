# Domain Implementation Contract

## Purpose

This contract directs Claude, Codex, and human contributors when translating the TaskControl domain handbook into code.

It is not a request to generate only data classes. The implementation must preserve behaviour, lifecycle rules, provenance, and failure semantics.

## Required implementation shape

The domain should be organised so that:

- Entities and value objects contain local invariants.
- Domain services contain rules that span aggregates.
- Application services coordinate repositories, authorisation, transactions, audit, and adapters.
- Repository interfaces define persistence needs.
- Ports define scheduler, executor, secret, notification, monitoring, inventory, clock, and artefact-storage boundaries.
- Infrastructure adapters implement ports.
- FastAPI routes and Typer commands call application services.
- React consumes API contracts and does not implement domain truth.

## Minimum domain modules

```text
src/taskcontrol/
  domain/
    common/
    tasks/
    scheduling/
    configuration/
    execution/
    deployment/
    governance/
    integrations/
  application/
    commands/
    queries/
    services/
    ports/
  infrastructure/
    persistence/
    executors/
    schedulers/
    secrets/
    notifications/
    monitoring/
    inventory/
  api/
  cli/
```

Exact folder names may vary, but dependency direction must remain.

## Required value objects

Implement typed value objects or equivalent validated types for:

- Stable identifiers.
- Revision numbers.
- Schema versions.
- Content digests.
- UTC timestamps.
- IANA time zones.
- Durations.
- Cron expressions.
- Lifecycle states.
- Result classifications.
- Reason codes.
- Idempotency keys.
- Correlation identifiers.
- Secret references.
- Target selectors.

Avoid passing unvalidated dictionaries throughout the core.

## Required aggregate behaviours

### Task

- Create stable identity.
- Create draft revision.
- Publish revision after validation.
- Activate published revision.
- Suspend, resume, retire, and archive through legal transitions.
- Preserve revision history.

### Schedule and trigger

- Validate expressions and time zones.
- Preview occurrences.
- Create idempotent scheduled triggers.
- Evaluate eligibility and produce structured explanation.
- Represent skip and condition error without fake execution attempts.

### Configuration

- Resolve ordered layers deterministically.
- Show source trace.
- Detect conflict and template cycles.
- Keep secret values outside persisted resolution output.

### Execution

- Create execution from eligible request.
- Add immutable attempts.
- Enforce legal transitions.
- Derive final result from process and expected-outcome evidence.
- Support retry, timeout, cancellation, and unknown state honestly.

### Deployment

- Generate immutable side-effect-free plans.
- Render target artefacts through adapters.
- Apply exact approved plan.
- Record per-target results.
- Detect and classify drift.

### Governance

- Evaluate permissions.
- Require exact-digest approvals where configured.
- Write append-only audit events.

## Required application services

At minimum:

- TaskService.
- RevisionPublicationService.
- EligibilityService.
- ConfigurationResolutionService.
- ExecutionRequestService.
- ExecutionCoordinator.
- ExpectedOutcomeService.
- DeploymentPlanningService.
- DeploymentApplicationService.
- DriftService.
- ApprovalService.
- AuditService.
- NotificationDispatchService.

Do not create a single `TaskControlService` containing all behaviour.

## Repository contracts

Repositories should expose domain-oriented operations rather than generic ORM access.

Examples:

- `TaskRepository.get_with_revisions(task_id)`.
- `ExecutionRepository.reserve_concurrency_slot(...)`.
- `TriggerRepository.get_or_create_scheduled_occurrence(...)`.
- `DeploymentRepository.save_plan(...)`.
- `AuditRepository.append(event)`.

Application services should not issue raw SQL.

## Persistence expectations

- Use migrations from the beginning.
- Separate mutable roots from immutable revisions.
- Use foreign keys and uniqueness constraints for core invariants.
- Use optimistic version columns where concurrent changes matter.
- Persist current state plus transition history where operationally significant.
- Use an outbox table for asynchronous follow-up when introduced.
- Ensure SQLite development behaviour remains compatible with PostgreSQL semantics as far as practical.

## Public schemas

Pydantic/API schemas should be separate from domain entities.

Public schemas must:

- Have explicit versions where long-lived configuration is involved.
- Use stable enum values.
- Exclude secret values.
- Expose explanation and provenance.
- Represent partial and unknown states.
- Avoid returning ORM internals.

## Command handling sequence

A modifying application command should generally:

1. Validate request schema.
2. Build RequestContext.
3. Authorise principal and scope.
4. Load aggregates.
5. Apply domain behaviour.
6. Persist atomically.
7. Append audit event.
8. Add outbox events if needed.
9. Commit.
10. Perform or enqueue external side effects.
11. Reconcile and persist side-effect result.

## Testing contract

### Unit tests

Must cover pure domain behaviour without database or web frameworks.

### Persistence integration tests

Must cover mappings, constraints, transactions, optimistic concurrency, and migrations.

### Adapter contract tests

Every adapter category should have a reusable contract suite.

### Application-service tests

Must verify authorisation, audit, idempotency, and transaction behaviour.

### End-to-end vertical slices

Required slices:

1. Create task, publish revision, run locally, inspect result.
2. Schedule preview with calendar and condition skip.
3. Resolve profiles with trace and secret reference.
4. Process exits zero but expected file outcome fails.
5. Plan and apply managed local cron artefact.
6. Detect manual cron drift.
7. Deny unauthorised deployment.

## Prohibited shortcuts

Do not:

- Store all domain state in one JSON column without queryable keys and constraints.
- Mutate published revisions.
- Let routes call ORM sessions directly for business actions.
- Treat skipped triggers as successful executions.
- Treat exit code zero as unconditional success.
- Put plaintext secrets in configuration records.
- Execute arbitrary shell strings by default.
- Apply deployments without a stored plan.
- Hide partial deployment results.
- Replace classified errors with generic exceptions.
- Build a UI-only mock that bypasses real execution and persistence.

## Incremental implementation rule

A smaller working vertical slice is acceptable when it preserves domain boundaries. An incomplete but honest implementation must:

- Mark unsupported capabilities explicitly.
- Return typed `UnsupportedCapability` errors.
- Maintain extension points.
- Record remaining work in `development/IMPLEMENTATION_STATUS.md`.
- Avoid pretending placeholders are complete.

## Definition of domain-ready

The domain implementation is ready for broader application development when:

- Core aggregates and value objects exist.
- Lifecycle transitions are tested.
- Immutable revisions work.
- Eligibility explanations work.
- Configuration resolution with provenance works.
- Execution result derivation works.
- Deployment plans are immutable and diffable.
- Authorisation and audit are applied through application services.
- API/CLI can exercise at least one complete local vertical slice.

## Required self-review

Before claiming completion, the coding agent must answer:

- Did any framework-specific type leak into the domain?
- Can every execution identify the exact revision and configuration versions used?
- Can operators distinguish skip, process failure, timeout, outcome failure, and unknown?
- Can a deployment be reviewed before application?
- Can configuration values explain their origins?
- Are secrets absent from API responses, logs, audit, and artefact previews?
- Are state transitions explicit and tested?
- Are unsupported future capabilities honest rather than simulated?