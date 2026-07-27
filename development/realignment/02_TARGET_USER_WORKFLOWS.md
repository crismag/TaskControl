# Target User Workflows

- Status: Proposed
- Purpose: test the product against concrete behaviour rather than framework abstractions

## Workflow A — Create a scheduled job without cron knowledge

An operator creates a task through a web form, CLI, API, or task file.

They provide:

- name and purpose;
- runnable or command;
- schedule in a human-friendly form;
- working directory and configuration;
- owner and criticality;
- optional retry, timeout, and notification policy.

TaskControl validates the definition, previews the intended scheduler change, applies a managed cron artefact, and verifies the installed result.

The operator does not need to edit a crontab or type a runtime execution command for routine operation.

## Workflow B — Install a drop-in runnable

A developer places a package in an approved directory:

```text
/opt/taskcontrol/drop-ins/nightly-report/
    task.yaml
    run.sh
```

TaskControl discovers the package, validates permissions and metadata, registers it, and either generates a dedicated cron entry or makes it eligible for a cron-invoked dispatcher according to the selected deployment strategy.

Invalid or incomplete packages are quarantined or reported; they are never silently activated.

## Workflow C — Import and understand existing cron jobs

An administrator asks TaskControl to inspect existing user or system cron sources.

TaskControl identifies:

- managed entries;
- unmanaged entries;
- duplicates and conflicts;
- missing runnables or directories;
- probable ownership and repository links when discoverable;
- definitions that differ from installed state.

The administrator may adopt an existing entry into TaskControl without immediately rewriting it.

## Workflow D — Remote asynchronous work submission

A remote application submits a work item through the API:

```http
POST /api/v1/work-items
```

The request identifies a registered task type, payload, idempotency key, and optional priority or not-before time.

TaskControl persists the item and immediately returns an identifier and accepted status. The caller does not wait for execution.

Cron later invokes a short-lived queue worker. The worker safely claims eligible work, executes the registered handler, records attempts and results, and transitions the item to a terminal or retry-wait state.

The caller can query status without knowing anything about cron or the target host.

## Workflow E — Accumulated pipeline processing

A batch of messages or requests accumulates in durable storage. Cron wakes a worker at a configured interval. The worker processes a bounded number of items so one invocation cannot monopolise the host.

A successful work item may create or release a later work item. Initial support should favour explicit linear next-step or parent/child relationships rather than a general-purpose graph language.

## Workflow F — Operate while the control plane is unavailable

The web UI or API becomes unavailable.

Already-installed cron artefacts continue to activate local jobs or queue workers. Task definitions and runnable wrappers needed for execution remain locally available.

Reporting to the central service is best effort where safe. Loss of the UI must not automatically prevent essential work from running.

The system must distinguish this case from failure of the local executable, task files, database, or required dependency.

## Workflow G — Inspect operational knowledge

An operator opens a task and sees:

- purpose and owner;
- source repository and runnable location;
- intended and installed schedules;
- target host or environment;
- last and next activation;
- recent attempts and outcomes;
- unresolved failures;
- dependencies and expected outputs;
- last review and change history;
- runbook and intervention guidance.

This knowledge is a core product outcome, not optional decoration.

## Workflow H — Detect and reconcile drift

TaskControl compares the desired task definition with the installed cron state and local runnable state.

It reports:

- missing or unexpected entries;
- changed schedules or commands;
- disabled jobs;
- unmanaged edits;
- missing or altered drop-in packages;
- configuration differences between environments.

The user receives a plan before apply. Reconciliation must be explicit and auditable.

## Workflow I — Manual run for testing or recovery

A user may deliberately request a one-off run from the UI, API, or CLI for validation, incident recovery, or development.

This is an administrative convenience, not the normal mental model for recurring jobs. Documentation must never present `taskctl execute <task>` as the primary way scheduled work operates.
