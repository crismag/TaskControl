# Reference Architecture

- Status: Proposed
- Purpose: describe the target shape without committing prematurely to implementation details

## System view

```text
Users, administrators, and remote applications
                    |
          Web UI / CLI / REST API
                    |
          TaskControl control plane
                    |
   +----------------+------------------+
   |                |                  |
Task catalogue   Cron manager      Work-item queue
and knowledge    and deployment    and pipeline state
   |                |                  |
   |          managed artefacts         |
   |                v                  |
   |              cron ----------------+
   |                |
   +----------------+
                    v
       short-lived execution boundary
                    |
      runnable / handler / queue worker
                    |
     logs, attempts, evidence, outcomes
                    |
          persistence and audit
```

## Architectural components

### Task catalogue

Stores desired task identity, immutable revisions, runnable metadata, schedule intent, ownership, criticality, documentation, configuration references, and lifecycle status.

### Drop-in discovery

Scans configured directories, validates packages, computes content identity, and proposes registration or update. Discovery does not automatically trust or execute arbitrary files.

### Cron management adapter

Owns cron-specific rendering, validation, installation, import, adoption, enable/disable, verification, and drift detection. Cron must be treated as an external execution substrate behind an explicit scheduler-management port.

### Work-item queue

Persists remotely submitted asynchronous work, idempotency keys, eligibility, claims, attempts, retry timing, results, and limited next-step relationships.

### Execution services

Wave 3 functionality belongs here. Execution services may launch a command or handler, apply timeout and cancellation policy, capture output, classify outcomes, and record attempts. They are invoked by cron-triggered commands, queue workers, or explicit administrative run-now operations.

### Operational knowledge and audit

Maintains task ownership, source, runbook, review status, intended versus installed state, change history, attempt history, and intervention evidence.

### API and application services

Provide authenticated commands and queries without leaking persistence, cron syntax, or execution implementation into external clients.

## Process model

TaskControl should not require one immortal scheduler process for recurring activation.

Supported process shapes include:

1. **Control-plane process** — web/API process used for management and inspection.
2. **Cron management command** — short-lived plan/apply/import/verify operation.
3. **Scheduled task wrapper** — short-lived execution of one managed task.
4. **Queue worker invocation** — short-lived bounded processing of eligible work items.
5. **Drop-in reconciler** — short-lived discovery and reconciliation operation, optionally activated by cron.

A deployment may run the API continuously, but recurring jobs must not depend solely on that process staying alive.

## Dependency direction

The domain and application layers must express scheduler and execution needs through ports. Cron, SQL persistence, filesystem discovery, shell execution, and HTTP are adapters.

The domain must not import cron libraries, FastAPI, SQLAlchemy, filesystem watchers, or operating-system process APIs.

## Scheduling models

Two cron-backed models are valid and may coexist:

### Dedicated-entry model

TaskControl creates a managed cron entry for an individual recurring task.

```text
cron -> stable TaskControl wrapper -> runnable
```

This offers clear scheduler visibility and independent activation.

### Dispatcher model

TaskControl installs a small number of stable cron entries that invoke a reconciler or queue worker. The worker discovers or claims eligible work.

```text
cron -> bounded dispatcher/worker -> eligible local or queued work
```

This is useful for drop-ins and accumulated asynchronous messages. It must not become an in-memory replacement scheduler. Eligibility and claiming must be durable and inspectable.

## Availability principle

The design separates the control plane from the execution path:

- UI/API downtime should not remove already-installed cron schedules;
- locally deployed task definitions and wrappers should remain usable;
- queue execution may require local persistence availability;
- remote reporting may be best effort, but execution semantics and data-loss behaviour must be explicit;
- reconciliation after recovery must preserve auditability.

## Security boundary

Remote submission must never permit arbitrary command execution by default. API clients submit against registered task types or approved templates. Creating or changing executable definitions requires stronger authorisation than submitting a work item.

Drop-in activation must validate ownership, permissions, allowed roots, manifest schema, executable type, and secret references before deployment.
