# Reference Architecture

## Architectural style

Begin with a modular Python monolith that can run locally, then separate services only when deployment scale or reliability requires it. Use ports-and-adapters boundaries around schedulers, executors, persistence, deployment transports, calendars, monitoring, notifications, and secrets.

## Major layers

### Interfaces
- CLI (`taskctl`)
- REST API
- web application
- import/export tools

### Application services
- task authoring and validation
- schedule preview
- profile resolution
- run-condition evaluation
- deployment planning
- execution orchestration
- history and audit queries
- monitoring-definition generation

### Domain engine
- task definitions and versions
- triggers and calendars
- profiles and inheritance
- run conditions and switches
- deployments and identities
- execution attempts and outcomes
- expectations and monitoring bindings

### Adapters
- scheduler: cron, systemd; later Kubernetes and Windows
- executor: shell, Python, Tcl, executable, HTTP; later SQL and containers
- persistence: SQLite and PostgreSQL
- deployment: local filesystem, repository export, SSH; later native agent
- monitoring: generic contract and Nagios export first
- notification: console/log first, then email/webhook
- secrets: environment/file development adapter, then external providers

## Runtime flow

1. A scheduler or API creates a trigger event.
2. The runtime resolves the task definition and deployment instance.
3. Configuration profiles are merged deterministically.
4. Run conditions are evaluated in a defined order.
5. The runtime records an execution attempt even when execution is skipped.
6. If allowed, the selected executor runs with timeout, locking, environment, working-directory, and output-capture controls.
7. The result is classified into an explicit outcome.
8. Expectations may be evaluated locally or exported to monitoring.
9. Logs, events, and audit records are persisted.
10. Notifications are dispatched according to policy.

## Local-first topology

For the first release:

```text
Browser / CLI
      |
Python API and application services
      |
SQLite + local artefact store
      |
Local scheduler adapter
      |
Managed runner
      |
Bash / Python / Tcl / executable
```

The local scheduler should invoke TaskControl's runner rather than duplicate policy and logging logic in every generated script.

Example:

```cron
0 7 * * 1-5 /usr/local/bin/taskctl run --deployment-id dep_123
```

## Central management topology

Later:

```text
Web UI -> API -> PostgreSQL
              -> worker/deployment service
              -> SSH or TaskControl agent
              -> local scheduler and runtime
```

Local execution must remain capable of running during temporary control-plane unavailability using an approved deployment bundle.

## Language strategy

- Python 3.12+ for the reference control plane and runtime.
- TypeScript for the web client.
- YAML or JSON for portable declarative definitions, with JSON Schema generated or maintained for validation.
- Shell, Python, Tcl, executable, and HTTP execution adapters.
- Go or Rust may later implement a native host agent using a versioned language-neutral protocol.
- C++ is not part of the initial stack unless a concrete integration requires it.

## Security boundaries

- Never interpolate untrusted command text into a shell implicitly.
- Prefer argument arrays and explicit shell mode.
- Separate task authorship, deployment authorization, and execution identity.
- Avoid storing plaintext secrets in task definitions, generated artefacts, logs, or audit events.
- Record configuration provenance without leaking secret values.
- Validate filesystem paths, ownership, permissions, and allowed execution adapters.
- Sign or checksum deployment bundles in later multi-host phases.

## Reliability boundaries

- Idempotent artefact generation.
- Atomic scheduler-file updates.
- Rollback on deployment failure.
- Locking for overlap control.
- Durable execution records.
- Deterministic profile merge order.
- Stable status and error taxonomy.
- UTC persistence with explicit local timezone display and calendar evaluation.

## Extension constraints

New platform support must be added through adapters, not conditionals spread throughout domain logic. New run conditions must return structured decisions containing allowed/denied state, reason code, human explanation, and relevant evidence.
