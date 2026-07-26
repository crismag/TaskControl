# Targets, Inventory, Deployments, and Drift

## Purpose

The deployment domain transforms versioned operational intent into target-specific artefacts and applies those artefacts safely, visibly, and reversibly.

The deployment model must support a local workstation first while preserving the same conceptual flow for fleets, clusters, regions, and federated control planes.

## Target

A Target is a logical execution destination.

Examples:

- The local machine.
- A Linux host.
- A Windows server.
- A Kubernetes namespace.
- A remote agent.
- A managed application environment.

### Attributes

- `target_id`.
- Name and description.
- Target type.
- Platform.
- Environment reference.
- Inventory-group memberships.
- Labels and selectors.
- Connection or agent reference.
- Scheduler capabilities.
- Executor capabilities.
- Deployment capabilities.
- Lifecycle state.
- Last observed state and timestamp.
- Ownership and governance metadata.

### Lifecycle states

- Discovered.
- Registered.
- Active.
- Maintenance.
- Unreachable.
- Retired.
- Archived.

A target marked Maintenance should normally deny automatic executions while allowing controlled diagnostics.

## Platform

Platform describes operating-system and runtime characteristics relevant to rendering and execution.

Recommended fields:

- Operating-system family and version.
- Architecture.
- Shell capabilities.
- Python/Tcl/runtime availability.
- Scheduler types.
- Path conventions.
- Service-manager capabilities.
- Container capabilities.
- Agent version.

Target observations are time-sensitive facts and should not be mistaken for static configured intent.

## InventoryGroup

An InventoryGroup is a named target grouping used for selection, inherited defaults, reporting, and bulk planning.

Group membership may be:

- Explicit.
- Label-selector based.
- Imported from an external inventory.
- Computed by a plugin.

Group hierarchy must be acyclic. Selection results should be materialised into a DeploymentPlan so later inventory changes do not alter an already approved plan.

## TargetSelector

A TargetSelector identifies candidate targets using explicit identifiers, groups, labels, environment, platform, or plugin-defined rules.

Selection must produce:

- Matched targets.
- Excluded targets and reasons.
- Capability mismatches.
- Selector version or query.
- Observation timestamp.

## DeploymentPlan

A DeploymentPlan is immutable and side-effect free. It describes exactly what TaskControl intends to change.

### Attributes

- `deployment_plan_id`.
- Task and revision identifiers.
- Selected targets.
- Adapter type and version.
- Generated artefacts per target.
- Desired-state digest.
- Observed-state digest when available.
- Proposed operations.
- Validation results.
- Risks and warnings.
- Approval requirements.
- Rollback strategy.
- Creation actor and time.
- Expiry time.

### Proposed operation types

- Create artefact.
- Update artefact.
- Remove artefact.
- Enable schedule.
- Disable schedule.
- Install runtime package.
- Update profile materialisation metadata.
- No change.
- Unsupported.

### Plan requirements

A plan must be reviewable before application. It should include human-readable diffs and machine-readable operations.

It must not contain plaintext secrets.

A plan should become stale when:

- Referenced revision changes.
- Target observed state changes materially.
- Adapter version is no longer supported.
- Approval expires.
- Plan expiry passes.

## GeneratedArtefact

A GeneratedArtefact is a target-specific representation derived from domain intent.

Examples:

- Crontab fragment.
- systemd service and timer units.
- Kubernetes CronJob manifest.
- Windows scheduled-task definition.
- TaskControl execution wrapper.
- Environment file containing only safe values or secret references.
- Monitoring configuration.

### Attributes

- Artefact identifier.
- Type and format.
- Target path or installation location.
- Content digest.
- Generator and version.
- Source revision digest.
- File permissions and ownership.
- Validation status.
- Redacted preview.

Generated artefacts should include provenance comments or metadata where the external format permits.

## Deployment

A Deployment is a recorded attempt to apply one DeploymentPlan.

### Attributes

- `deployment_id`.
- Plan identifier and digest.
- Requesting principal.
- Approval references.
- Start and end times.
- Overall state.
- Per-target deployment results.
- Rollback result.
- Audit correlation identifier.

### States

- Requested.
- PendingApproval.
- Applying.
- PartiallyApplied.
- Applied.
- Failed.
- RollingBack.
- RolledBack.
- RollbackFailed.
- Cancelled.
- Unknown.

### Per-target result

Each target result records:

- Operations attempted.
- Before and after digests.
- Validation output.
- Backup or rollback reference.
- Error classification.
- Final observed state.

A multi-target deployment must not hide partial success.

## Local cron initial implementation

The first production-capable adapter may target local cron, but it must still follow plan/apply/observe semantics.

Required behaviour:

1. Render a managed crontab fragment or managed block.
2. Validate syntax.
3. Show a diff.
4. Back up current managed state.
5. Apply only after explicit confirmation or authorised non-interactive flag.
6. Verify installed state.
7. Record deployment and audit events.
8. Support removal and rollback.

TaskControl must not overwrite unrelated user crontab entries.

A managed marker strategy may be used, but markers must be stable and resilient to repeated application.

## DeploymentPackage

For portable execution, TaskControl may generate a package containing:

- Revision manifest.
- Wrapper runner.
- Safe configuration metadata.
- Required scripts or references.
- Checksums.
- Expected-outcome definitions.
- Scheduler artefacts.
- Monitoring artefacts.

Packages should be deterministic where possible and signed in future enterprise modes.

## DriftObservation

Drift is the difference between desired state and observed state.

### Drift types

- Missing artefact.
- Modified artefact.
- Unexpected artefact.
- Disabled schedule.
- Wrong owner or permissions.
- Wrong revision digest.
- Unsupported adapter version.
- Target capability drift.
- Unobservable state.

### Attributes

- Observation identifier.
- Target.
- Desired-state reference.
- Observed-state snapshot.
- Drift classification.
- Severity.
- Evidence.
- Detection time.
- Reconciliation status.

### Reconciliation policy

Possible policies:

- Report only.
- Require manual apply.
- Automatically reconcile low-risk drift.
- Quarantine target.

The initial application should report drift and require explicit reconciliation.

## Capability matching

Before planning, TaskControl must compare revision requirements against target capabilities.

Examples:

- Requested Python executor but no interpreter or agent capability.
- systemd deployment requested on a non-systemd host.
- Required working directory unavailable.
- Expected-outcome evaluator unsupported.

Capability mismatch must appear in the plan and block unsafe application.

## Persistence guidance

Keep configured target metadata separate from observed target facts. Store immutable deployment plans and append-oriented deployment results. Store artefact content or references with digests sufficient for review and rollback.

## API guidance

Recommended resources:

- `/targets`.
- `/inventory-groups`.
- `/deployment-plans`.
- `/deployments`.
- `/drift-observations`.
- `/targets/{target_id}/capabilities`.

Recommended commands:

- Plan deployment.
- Approve plan.
- Apply plan.
- Roll back deployment.
- Observe target.
- Reconcile drift.

## CLI guidance

```text
taskctl target register local
taskctl target inspect local
taskctl deploy plan <task> --target local
taskctl deploy diff <plan>
taskctl deploy apply <plan>
taskctl deploy rollback <deployment>
taskctl drift check --target local
```

## UI guidance

The deployment UI should show:

- Revision and target scope.
- Proposed changes.
- Rendered artefacts.
- Security warnings.
- Approval state.
- Apply progress per target.
- Rollback availability.
- Desired versus observed state.
- Drift history.

## Audit requirements

Audit:

- Target registration and retirement.
- Inventory membership changes.
- Plan creation.
- Approval.
- Apply, rollback, and reconciliation.
- Manual target-state override.
- Drift acknowledgement.

## Future extensions

- Remote agents.
- Signed deployment bundles.
- Progressive rollout and canaries.
- Environment promotion.
- Regional deployment coordinators.
- Offline target reconciliation.
- External inventory synchronisation.
- High-availability desired-state controllers.