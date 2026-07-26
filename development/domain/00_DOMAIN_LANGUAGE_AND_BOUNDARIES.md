# Domain Language and Boundaries

## Objective

TaskControl must use a precise ubiquitous language across code, API, CLI, UI, documentation, tests, and operational logs. Similar-sounding concepts are not interchangeable.

## Product domain statement

TaskControl manages the definition, resolution, deployment, execution, observation, and governance of scheduled operational tasks across one or more execution targets.

It does not own the business logic inside user scripts. It owns the operational contract around those scripts.

## Core bounded contexts

### 1. Definition Context

Owns reusable operational intent.

Primary concepts:

- Task
- TaskRevision
- TaskCollection
- ActionSpecification
- ExecutionPolicy

It answers:

- What should run?
- Which immutable definition version is active?
- What runtime controls apply?

It must not directly execute processes or mutate scheduler files.

### 2. Scheduling Context

Owns when an execution may be requested.

Primary concepts:

- Schedule
- Trigger
- Calendar
- RunCondition
- TimeWindow

It answers:

- When is the task nominally due?
- Is the trigger occurrence eligible?
- Why was a due occurrence skipped?

A schedule does not mean execution is guaranteed. It produces candidate trigger occurrences.

### 3. Configuration Context

Owns reusable runtime configuration and deterministic resolution.

Primary concepts:

- Profile
- ConfigurationLayer
- VariableDefinition
- SecretReference
- ResolutionTrace

It answers:

- Which values are available to the task?
- Which layer supplied each value?
- Which values are sensitive?

It must never persist resolved secret values in ordinary domain records or logs.

### 4. Execution Context

Owns concrete runtime work and its evidence.

Primary concepts:

- ExecutionRequest
- Execution
- ExecutionAttempt
- ProcessResult
- ExpectedOutcome
- OutcomeEvaluation
- Evidence

It answers:

- What exact revision ran?
- Where and with which resolved non-secret configuration metadata?
- Did the process start, finish, time out, or fail?
- Did the intended operational outcome occur?

### 5. Deployment Context

Owns transformation of intent into target-specific scheduler and runtime artefacts.

Primary concepts:

- Target
- InventoryGroup
- DeploymentPlan
- Deployment
- GeneratedArtefact
- DriftObservation

It answers:

- What should be installed where?
- What changes are proposed?
- What was applied?
- Does observed state match desired state?

### 6. Governance Context

Owns authority, approvals, and traceability.

Primary concepts:

- Principal
- User
- ServiceIdentity
- Role
- Permission
- ApprovalRequest
- ApprovalDecision
- AuditEvent

It answers:

- Who may perform an action?
- Which actions require approval?
- Who changed what, when, and why?

### 7. Integration Context

Owns external communication and extension points.

Primary concepts:

- Adapter
- Plugin
- NotificationRule
- NotificationDelivery
- MonitoringIntegration

It answers:

- How does TaskControl communicate with schedulers, executors, monitoring systems, and notification channels?

## Ubiquitous language

### Task

A stable logical identity representing operational intent. A Task is not a shell command, execution, or cron line.

### TaskRevision

An immutable snapshot of task configuration. Executions and deployments must reference a specific revision.

### TaskCollection

A named grouping used for organisation, bulk operations, inherited defaults, or deployment selection. It is not automatically a workflow or dependency graph.

### ActionSpecification

A declarative description of what an executor must do, such as run a command, invoke Python, call HTTP, or execute Tcl.

### Schedule

A reusable rule describing nominal due times. A schedule produces candidate triggers.

### Trigger

A concrete occurrence or request that may produce an execution. Trigger types include schedule, manual, API, retry, replay, or event.

### RunCondition

A deterministic predicate evaluated before execution permission is granted. It returns allow, deny, or error with evidence and reason.

### Calendar

A named set of business dates, holidays, open days, or exceptional sessions used by run conditions and schedule interpretation.

### Profile

A reusable set of non-secret values and secret references applied through explicit scope and precedence.

### Target

A logical execution destination. A target can initially represent the local machine and later a remote host, cluster, namespace, account, or managed agent.

### DeploymentPlan

A side-effect-free representation of intended changes, including rendered artefacts, diffs, validation results, risks, and required approvals.

### Deployment

A recorded attempt to apply a deployment plan to one or more targets.

### ExecutionRequest

A validated request to create an execution. It captures trigger, task revision, target selection, requester, and idempotency information.

### Execution

A durable operational record representing one requested run of one task revision on one target.

### ExecutionAttempt

One runtime attempt within an execution. Retry policies may produce multiple attempts.

### ProcessResult

The technical process outcome: exit code, signal, timing, standard output, standard error, timeout, or launch failure.

### ExpectedOutcome

A declarative operational assertion, such as file creation, freshness, content match, HTTP response, or runtime range.

### OutcomeEvaluation

The evaluation result for one expected outcome, with status, evidence, and reason.

### ExecutionResult

The final classified result derived from attempts and expected-outcome evaluations. It must distinguish success, failure, timeout, cancellation, skip, condition error, and outcome failure.

### Skip

A deliberate non-execution caused by a condition or policy. A skip is observable and reasoned; it is not silently treated as success or failure.

### Drift

A difference between desired deployed state and observed target state.

### AuditEvent

An append-only domain-significant record. It is separate from diagnostic application logs.

## Aggregate boundaries

### Task aggregate

Root: Task

Contains or references:

- Active revision identifier
- Revision history
- Lifecycle state
- Collection membership
- Ownership metadata

Revision content remains immutable.

### Schedule aggregate

Root: Schedule

Contains:

- Schedule expression
- Time zone
- Effective period
- Misfire policy
- Enabled state

Schedules may be reused by multiple task revisions when explicitly allowed.

### Profile aggregate

Root: Profile

Contains:

- Scoped variables
- Secret references
- Parent relationships if supported
- Version
- Enabled state

### Execution aggregate

Root: Execution

Contains:

- Attempts
- State transitions
- Trigger metadata
- Outcome evaluations
- Result classification
- Cancellation request metadata

Large log payloads may be stored externally but remain referenced from the aggregate.

### Target aggregate

Root: Target

Contains:

- Platform and capability metadata
- Connection or agent reference
- Labels
- Lifecycle state
- Last observation metadata

### Deployment aggregate

Root: Deployment

References an immutable DeploymentPlan and records application results per target.

## Dependency direction

- Definition may depend on shared value objects but not scheduling infrastructure.
- Scheduling may reference task identifiers but must not execute tasks.
- Configuration resolution may reference target, environment, and task scope through stable identifiers.
- Execution depends on resolved definitions but not on API or UI frameworks.
- Deployment depends on definitions, schedules, targets, and adapter contracts.
- Governance applies across all contexts through policies and audit events.
- Integrations depend on domain ports; domain code does not depend on integration implementations.

## Cross-context events

Recommended internal events include:

- TaskCreated
- TaskRevisionPublished
- TaskActivated
- TaskSuspended
- TriggerDue
- TriggerSkipped
- ExecutionRequested
- ExecutionStarted
- ExecutionAttemptFinished
- ExecutionCompleted
- DeploymentPlanned
- DeploymentApplied
- DeploymentFailed
- DriftDetected
- ApprovalRequested
- ApprovalDecided
- NotificationRequested

Events should carry identifiers and minimal immutable facts, not framework objects or secrets.

## Anti-corruption rules

External scheduler vocabulary must not leak into the core model.

Examples:

- `crontab line` becomes a GeneratedArtefact.
- `systemd unit` becomes a GeneratedArtefact.
- `Kubernetes CronJob` becomes a scheduler-adapter representation.
- `Nagios check` becomes a monitoring-integration representation.

Adapters translate domain intent into external models and translate observations back into TaskControl result types.

## Naming rules

- Use nouns for entities and value objects.
- Use commands for requested changes: `PublishTaskRevision`, `RequestExecution`.
- Use past-tense events for completed facts: `ExecutionStarted`.
- Avoid vague terms such as job, config, status, result, policy, or environment without a qualified domain meaning.
- Never use `success` without specifying process success or operational outcome success.

## Framework independence

Domain types must be usable in pure unit tests without starting a database, web server, message broker, scheduler, or operating-system process. ORM mappings and API schemas may adapt domain objects but must not define the business meaning.