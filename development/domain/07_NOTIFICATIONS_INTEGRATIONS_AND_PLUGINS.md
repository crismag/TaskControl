# Notifications, Integrations, and Plugins

- Document level: **1 — Architecture**
- Lifecycle state: Canonical

## Purpose

TaskControl must communicate with external systems without allowing external APIs to define the core domain. Integration contracts translate domain events and commands into scheduler, executor, monitoring, notification, inventory, and secret-provider operations.

## Adapter

An Adapter implements a core port for one external technology.

Initial adapter categories:

- Scheduler adapter.
- Executor adapter.
- Deployment adapter.
- Monitoring adapter.
- Notification adapter.
- Secret-provider adapter.
- Inventory adapter.
- Artefact-storage adapter.

### Adapter requirements

Every adapter declares:

- Adapter identifier.
- Semantic version.
- Contract version.
- Capabilities.
- Supported platforms.
- Configuration schema.
- Validation method.
- Health-check method.
- Failure classifications.
- Idempotency behaviour.

Adapters must return typed results. They must not force callers to parse arbitrary error strings.

## SchedulerAdapter

A SchedulerAdapter renders and manages target scheduler definitions.

Responsibilities:

- Validate schedule compatibility.
- Render scheduler artefacts.
- Preview changes.
- Apply and remove managed definitions.
- Observe installed state.
- Report drift.

The initial cron adapter must not own Task scheduling semantics. It translates a resolved schedule into cron-compatible artefacts and uses TaskControl wrappers for conditions and execution recording.

Future adapters:

- systemd timers.
- Windows Task Scheduler.
- Kubernetes CronJobs.
- External enterprise schedulers.

## ExecutorAdapter

An ExecutorAdapter starts, observes, terminates, and classifies task runtime actions.

Responsibilities:

- Validate ActionSpecification compatibility.
- Materialise a safe launch request.
- Start the process or remote operation.
- Stream or capture output.
- Support timeout and cancellation.
- Return ProcessResult.
- Expose capability metadata.

Initial executors:

- Shell/program executor.
- Python script/module executor.
- HTTP executor.

Tcl can initially use a generic program executor while preserving a named adapter boundary.

## MonitoringIntegration

Monitoring is not the same as execution history. A MonitoringIntegration communicates operational expectations and state to systems such as Nagios or Prometheus.

Possible responsibilities:

- Render passive or active check definitions.
- Submit execution status.
- Export metrics.
- Produce heartbeat or freshness signals.
- Correlate monitoring alerts with TaskControl executions.

Initial implementation may expose internal health and execution metrics plus webhook hooks. Nagios integration can later generate check definitions or passive results.

## NotificationRule

A NotificationRule describes when, to whom, and through which channel a notification should be sent.

### Trigger events

- Execution failed.
- Execution timed out.
- Required outcome failed.
- Task skipped for an exceptional reason.
- Repeated failures reached threshold.
- Deployment failed or partially applied.
- Drift detected.
- Approval requested or expiring.
- Target unreachable.
- Calendar source stale.

### Attributes

- Rule identifier.
- Scope.
- Event filters.
- Severity threshold.
- Recipient selectors.
- Channel.
- Deduplication window.
- Suppression or maintenance rules.
- Escalation policy.
- Template reference.
- Enabled state.

## NotificationDelivery

A NotificationDelivery records one delivery attempt.

Attributes:

- Delivery identifier.
- Source event.
- Rule.
- Channel.
- Redacted recipient metadata.
- Attempt number.
- State.
- Provider response reference.
- Created, sent, and completed timestamps.
- Failure classification.

States:

- Pending.
- Sending.
- Delivered.
- Failed.
- Suppressed.
- Deduplicated.
- Cancelled.

Notification failure must not rewrite the source execution result. It is a separate operational problem.

## Notification content

Notifications should include:

- Task and environment.
- Final classification.
- Target.
- Relevant timestamp.
- Concise reason.
- Link or identifier for investigation.
- Whether action is required.

They must exclude secrets and avoid dumping full logs.

## Deduplication and escalation

Repeated identical failures should be grouped using a stable fingerprint derived from task, target, classification, and reason code.

Escalation may occur based on:

- Consecutive failures.
- Duration unresolved.
- Environment severity.
- Business calendar or critical window.

The first implementation may provide simple immediate webhook notifications and persisted delivery history.

## Plugin

A Plugin is a packaged extension that contributes one or more adapters, evaluators, schemas, UI metadata, or domain-safe hooks.

### Plugin manifest

A plugin manifest includes:

- Plugin identifier and version.
- Publisher.
- Description.
- Compatible TaskControl versions.
- Contract versions implemented.
- Capabilities.
- Entry points.
- Configuration schemas.
- Required permissions.
- External dependencies.
- Integrity information.

### Plugin lifecycle

- Discovered.
- Installed.
- Validated.
- Enabled.
- Disabled.
- Failed.
- Uninstalled.

Installation does not imply enablement.

### Safety rules

- Plugins are untrusted by default.
- Configuration is schema validated.
- Plugin failures are isolated and classified.
- Plugins receive only required data and permissions.
- Secret access must be explicitly declared and authorised.
- Plugins cannot mutate core database tables directly.
- Plugins use published service contracts.
- Plugin enablement and upgrades are audited.

The Python-first version may use Python entry points, but public plugin configuration and result contracts should remain language-neutral JSON-compatible schemas.

## Webhooks

Outbound webhooks are a practical initial integration mechanism.

Webhook delivery must support:

- Signed requests.
- Timeout.
- Retry with bounded backoff.
- Idempotency identifier.
- Redacted persisted request metadata.
- Response classification.
- Disablement after repeated permanent errors according to policy.

Inbound webhooks, when added, must authenticate sources and map payloads through explicit schemas rather than arbitrary execution commands.

## Metrics and health

TaskControl should expose metrics such as:

- Executions by classification.
- Execution duration.
- Queue delay.
- Condition decisions.
- Deployment results.
- Drift count.
- Notification delivery failures.
- Adapter health.

Metric labels must avoid unbounded cardinality. Execution IDs and raw task arguments do not belong in metric labels.

## Integration failure taxonomy

- ConfigurationInvalid.
- AuthenticationFailed.
- AuthorisationFailed.
- DependencyUnavailable.
- Timeout.
- RateLimited.
- ProtocolError.
- UnsupportedCapability.
- PermanentRemoteError.
- TransientRemoteError.
- UnknownIntegrationError.

Retry decisions must use classification rather than string matching.

## Persistence guidance

Persist adapter registrations, plugin manifests, plugin state, notification rules, and delivery history. Keep provider credentials as secret references.

## API guidance

Recommended resources:

- `/integrations`.
- `/plugins`.
- `/notification-rules`.
- `/notification-deliveries`.
- `/monitoring`.
- `/adapter-capabilities`.

## CLI guidance

```text
taskctl plugin list
taskctl plugin validate <package>
taskctl plugin enable <id>
taskctl integration test <id>
taskctl notification rule create
taskctl notification delivery retry <id>
```

## UI guidance

The UI should show adapter health, declared capabilities, plugin trust warnings, configuration validation, notification history, and test-connection results.

## Audit requirements

Audit:

- Integration creation and credential-reference change.
- Plugin install, enable, disable, upgrade, and removal.
- Notification-rule changes.
- Manual delivery retry.
- Monitoring export configuration.

## Future extensions

- Sandboxed plugin processes.
- Signed plugin registry.
- Marketplace.
- gRPC agent adapters.
- Bidirectional event buses.
- Incident-management integrations.
- Email, Slack, Teams, PagerDuty, and SMS channels.
- OpenTelemetry traces and logs.
