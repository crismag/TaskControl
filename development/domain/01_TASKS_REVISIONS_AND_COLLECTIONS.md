# Tasks, Revisions, and Collections

## Purpose

The Task domain defines durable operational intent without tying that intent to one scheduler, operating system, runtime, or deployment mechanism.

## Task

A Task is the stable identity of an operational activity.

Examples:

- Generate the daily settlement report.
- Synchronise reference data.
- Remove expired temporary files.
- Invoke a health-check endpoint.

A Task must not be treated as a mutable bag of runtime fields. Changes produce immutable revisions.

### Required attributes

- `task_id`: globally stable identifier.
- `name`: human-readable name unique within its owning scope.
- `slug`: stable URL- and CLI-safe name.
- `description`: operational purpose and expected effect.
- `owner_id`: user, team, or service ownership reference.
- `lifecycle_state`: draft, active, suspended, retired, or archived.
- `active_revision_id`: currently selected published revision, when applicable.
- `created_at`, `created_by`.
- `updated_at`, `updated_by` for mutable Task metadata only.
- Optional labels, tags, collection memberships, and external references.

### Mutable Task metadata

The following may be updated without creating a revision when they do not alter execution semantics:

- Display name
- Description
- Tags
- Ownership
- Documentation links
- Collection membership

Changes that affect execution, scheduling, policy, configuration, deployment, or outcomes require a new TaskRevision.

### Lifecycle

#### Draft

The Task exists but has no active deployable revision. Draft tasks may be edited, reviewed, and deleted if no audit or dependency policy prevents deletion.

#### Active

The Task has an active published revision and may accept triggers, subject to schedule, condition, deployment, and target eligibility.

#### Suspended

No new ordinary executions should start. Existing executions may continue unless separately cancelled. Manual override behaviour must be explicit and permission-controlled.

#### Retired

The Task is intentionally withdrawn. Existing history and deployments remain visible. Reactivation should require an explicit transition and may require a new revision.

#### Archived

The Task is read-only and hidden from ordinary active views. It must not be physically deleted when referenced by executions, deployments, audit records, or approvals.

### Commands

- CreateTask
- RenameTask
- ChangeTaskOwnership
- AddTaskToCollection
- RemoveTaskFromCollection
- PublishTaskRevision
- ActivateTaskRevision
- SuspendTask
- ResumeTask
- RetireTask
- ArchiveTask

### Queries

- GetTask
- ListTasks
- GetActiveTaskRevision
- ListTaskRevisions
- CompareTaskRevisions
- ListTasksByCollection
- ListTasksByOwner
- ExplainTaskEligibility

## TaskRevision

A TaskRevision is an immutable, versioned snapshot of all execution-relevant intent.

### Required attributes

- `revision_id`: stable identifier.
- `task_id`: parent Task.
- `revision_number`: monotonically increasing within the Task.
- `schema_version`: version of the public revision schema.
- `publication_state`: draft, published, superseded, withdrawn.
- `created_at`, `created_by`.
- `published_at`, `published_by`, when published.
- `change_summary`.
- `action_specification`.
- Schedule references or inline schedule binding.
- Profile and configuration bindings.
- Run-condition bindings.
- Target selector or target binding.
- Execution controls.
- Expected outcomes.
- Notification bindings.
- Deployment settings.

### Immutability rule

After publication, revision content must never be edited in place. Corrections produce a new revision.

Draft revision editing may use optimistic concurrency. Publishing freezes the content and computes a canonical content digest.

### Publication validation

A revision may be published only when:

- The action specification is valid.
- Referenced profiles, calendars, conditions, targets, and plugins exist or are explicitly marked as deferred external dependencies.
- Required secret references are syntactically valid.
- Timeout and retry values are within configured limits.
- Expected outcomes use supported evaluators.
- Target capabilities satisfy the executor and scheduler requirements, or publication explicitly permits unresolved target selection.
- No prohibited plaintext secret is detected.
- The schema version is supported.

### Activation

Publishing does not automatically activate a revision unless an explicit configuration allows it.

Activation must:

- Record the previous active revision.
- Record actor, reason, and timestamp.
- Validate deployment implications.
- Emit an audit event.
- Preserve running executions on their original revision.

### Supersession

When a newer revision becomes active, the former revision becomes superseded but remains executable for replay only when policy permits.

### Content digest

A deterministic digest should be generated from canonical revision content. The digest supports:

- Deployment integrity checks.
- Drift detection.
- Execution provenance.
- Reproducibility.
- Comparison across control planes.

Secret values must never participate directly; secret reference identifiers and optional versions may participate.

## ActionSpecification

The action specification describes what should be executed, independent of scheduler.

### Common fields

- `executor_type`: shell, python, tcl, executable, http, or plugin-defined.
- `entrypoint`: command, module, script, URL, or executable reference.
- `arguments`: ordered values or named parameters.
- `working_directory`.
- `environment_bindings`.
- `stdin_policy`.
- `output_capture_policy`.
- `platform_requirements`.
- `required_capabilities`.

### Shell action

Must support a safe argument-vector form. A raw shell-string mode may exist only as an explicit elevated-risk option.

Recommended representation:

```yaml
executor_type: shell
program: /usr/bin/bash
arguments:
  - /opt/tasks/generate_report.sh
  - --date
  - "{{ trigger.business_date }}"
```

### Python action

May run a script or module. The domain must not require the TaskControl server interpreter to be the target interpreter.

### HTTP action

Must define method, endpoint reference, headers through safe configuration, body template, timeout, response handling, and expected status ranges.

### Plugin-defined action

Must declare plugin identifier, contract version, capability requirements, and validated configuration.

## Execution controls

A TaskRevision may define:

- Timeout.
- Retry policy.
- Backoff strategy.
- Maximum concurrent executions.
- Overlap policy.
- Queue or reject policy.
- Cancellation grace period.
- Process termination policy.
- Working-directory policy.
- Output size limits.
- Resource hints.

### Overlap policies

- Allow: concurrent executions may overlap.
- Forbid: reject or skip when another execution is active.
- Queue: wait until prior execution finishes.
- Replace: cancel or supersede prior execution only when explicitly supported and authorised.

The first version should implement allow and forbid reliably before adding queue or replace.

## TaskCollection

A TaskCollection groups Tasks for organisation and controlled bulk behaviour.

### Uses

- Navigation and filtering.
- Ownership grouping.
- Shared profile bindings.
- Common target selectors.
- Bulk suspension or deployment planning.
- Reporting.

### Non-goals

A collection is not inherently:

- A dependency graph.
- A transaction boundary.
- A sequential workflow.
- A permission boundary unless explicitly configured.

### Attributes

- `collection_id`.
- Name and slug.
- Description.
- Owner.
- Parent collection, if hierarchy is supported.
- Labels.
- Default bindings.
- Lifecycle state.

### Inheritance

Collection defaults must be explicit, traceable, and overridable according to the configuration precedence model. The resolved TaskRevision should expose the source of each inherited value.

Circular collection inheritance is prohibited.

## Validation rules

- Task names are unique within scope.
- Slugs are immutable by default after external use; aliases may support rename.
- Revision numbers never decrease or repeat.
- Published content cannot mutate.
- An active Task must reference a published revision.
- Archived Tasks cannot accept new ordinary triggers.
- A Task cannot be physically deleted while referenced.
- Collection cycles are invalid.
- Unsupported executor types block publication unless an extension contract exists.
- Raw shell interpolation must be flagged and restricted.

## Persistence guidance

Use separate records for Task and TaskRevision. Store revision payloads in normalised tables, structured JSON, or a hybrid, but preserve:

- Immutable snapshots.
- Queryable core fields.
- Canonical schema version.
- Digest.
- References to child definitions.

Do not overwrite active revision data when editing drafts.

## API representation

Recommended resources:

- `POST /tasks`
- `GET /tasks`
- `GET /tasks/{task_id}`
- `PATCH /tasks/{task_id}` for metadata only.
- `POST /tasks/{task_id}/revisions`
- `GET /tasks/{task_id}/revisions`
- `GET /tasks/{task_id}/revisions/{revision_id}`
- `POST /tasks/{task_id}/revisions/{revision_id}/publish`
- `POST /tasks/{task_id}/activate`
- `POST /tasks/{task_id}/suspend`
- `POST /tasks/{task_id}/resume`
- `GET /tasks/{task_id}/eligibility`

Use explicit action endpoints for lifecycle transitions rather than arbitrary status patching.

## CLI representation

Examples:

```text
taskctl task create
taskctl task list
taskctl task show <task>
taskctl task revision create <task>
taskctl task revision diff <task> <a> <b>
taskctl task revision publish <task> <revision>
taskctl task activate <task> --revision <revision>
taskctl task suspend <task> --reason "maintenance"
```

## UI representation

The Task details page should show:

- Current lifecycle state.
- Active revision.
- Draft revision, if any.
- Schedule summary.
- Run conditions.
- Target scope.
- Profile sources.
- Last execution.
- Last successful operational outcome.
- Deployment status and drift.
- Revision history with comparison.
- Audit timeline.

The editing interface must make clear whether the user is editing Task metadata or creating a new revision.

## Audit requirements

Audit at minimum:

- Task creation.
- Metadata changes.
- Draft creation.
- Revision publication.
- Activation and rollback.
- Suspension and resume.
- Retirement and archival.
- Collection membership changes.

Audit records should include actor, reason, correlation identifier, before/after references, and affected identifiers.

## Future extensions

- Revision branches and review workflows.
- Task templates.
- Parameterised task instances.
- Dependency graphs.
- Event-driven triggers.
- Promotion across environments.
- Signed revisions.
- Marketplace-distributed plugins and templates.
- Policy-as-code validation.

These extensions must build on immutable revisions rather than replacing them.