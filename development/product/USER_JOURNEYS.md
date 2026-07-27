# User Journeys

- Document level: **0 — Identity**
- Governed by: `PRODUCT_SCOPE.md`, `PRODUCT_ROADMAP.md`
- Related: `USERS_AND_USE_CASES.md` (who), this document (what they do), ADR 0022 (cron owns activation)

## Purpose

This document grounds TaskControl in real operational journeys. Contributors and coding agents use these examples to test whether a proposed abstraction is useful rather than merely elegant.

## How to read the phase markers

Each journey carries the phase in which it becomes deliverable. A journey marked Phase 2 or later is **not** Phase 1 scope; it constrains the design so that the capability remains reachable, and its supporting capability is registered in `DEFERRED_CAPABILITIES.md`.

Phase 1 journeys: 1, 2, 3, 6, 7, 8, 9, 13, 14, 15 — note that **15 (crontab import and adoption) is now Phase 1**, because adopting an existing estate is core to a cron-backed product rather than a later convenience. Every feature proposal should be tested against at least one Phase 1 journey plus Journey 13.

## Journey 1: Personal scheduled task — **Phase 1**

A developer wants a Python report to run every weekday at 08:00 on a Linux workstation.

Expected flow:

1. Create a Task named `daily-project-report`.
2. Select the Python execution adapter.
3. Select the script and arguments.
4. Define a weekday schedule at 08:00 in the local time zone.
5. Preview the next scheduled runs, the resolved configuration, and the **managed cron
   artefact TaskControl will install**.
6. Run a validation and an administrative test execution.
7. Apply the managed cron entry, which TaskControl verifies by reading it back.
8. Cron activates the task; TaskControl records the outcome.
9. View execution history and logs.
10. Disable, update, or archive the task, and the managed entry follows.

Minimum value: easier and safer than hand-editing a crontab, without hiding what was
installed. The developer never types a cron expression, and the job keeps running whether or
not TaskControl's web process is up.

## Journey 2: Existing shell script with profile guards — **Phase 1**

An operations engineer has an established shell script that currently sources a shared profile and calls helper functions such as `ifholiday` before doing work.

Expected flow:

1. Register the existing script without rewriting it.
2. Model environment variables as a reusable Runtime Profile.
3. Model the holiday check as a Calendar-backed Run Condition.
4. Preview a generated wrapper that resolves the profile, evaluates conditions, records the decision, and invokes the original script.
5. Preserve the original script as the work implementation while moving cross-cutting operational behaviour into TaskControl.
6. Record `SKIPPED_CALENDAR_CLOSED` explicitly rather than relying on a silent early exit.

## Journey 3: Production file delivery — **Phase 1**

A task generates a report that must exist by 06:30.

The process returning zero is insufficient. TaskControl should support:

- a schedule at 06:00;
- a maximum runtime of 20 minutes;
- an expected file path;
- minimum file size;
- maximum data age;
- optional checksum or content validator;
- notification if the expected outcome is not satisfied;
- separate process and outcome status.

## Journey 4: Multi-host deployment — **Phase 3**

An administrator manages the same task on ten Linux hosts.

Expected capabilities:

- define the task once;
- target an inventory group;
- preview per-host effective configuration;
- generate a deployment plan;
- show additions, changes, and removals;
- apply with controlled concurrency;
- record host-level results;
- retry only failed hosts;
- detect drift after deployment;
- roll back to a previous revision.

## Journey 5: Mixed scheduler platforms — **Phase 3**

An organisation needs comparable operations on Linux cron, Linux systemd, Kubernetes, and Windows.

The Task definition should remain stable. Platform-specific Scheduler Adapters generate native artefacts. Unsupported semantics must be reported during planning rather than silently approximated.

Example: a scheduler that cannot express a complex calendar condition should generate a frequent trigger plus a TaskControl runtime guard rather than dropping the condition.

## Journey 6: Exchange calendar operation — **Phase 1**

A market-data task runs according to the business calendar of a particular exchange.

Requirements:

- named calendars;
- holidays and exceptional closures;
- early-close metadata;
- time-zone awareness;
- calendar revisions and provenance;
- reusable conditions such as `calendar.is_open`;
- explainable evaluation output;
- ability to test a historical or future date.

## Journey 7: Maintenance switch — **Phase 1**

An operator needs to stop a family of tasks without editing each schedule.

TaskControl should allow a Runtime Switch or inherited Run Condition at an application, environment, host group, or task level. Every skipped execution must identify the switch, its resolved value, origin, and reason.

## Journey 8: Dependency-aware execution — **Phase 1**

A downstream task should run only when a required upstream operation has completed successfully and its output remains fresh.

The first version may support simple dependency checks without becoming a full DAG workflow engine. The design must distinguish:

- scheduler trigger;
- permission to start;
- dependency state;
- execution ordering;
- expected outcomes.

Avoid turning TaskControl into a general-purpose data pipeline orchestrator unless later product decisions explicitly expand the scope.

## Journey 9: Approval-controlled production deployment — **Phase 1**

A developer edits a task used in production.

Expected lifecycle:

1. Save a new task revision.
2. Validate it.
3. Generate a deployment plan.
4. Review generated artefacts and impact.
5. Request approval.
6. Approver accepts or rejects with comments.
7. Apply the approved immutable plan.
8. Record audit events.
9. Verify deployment state.

Approval is attached to a specific plan or revision, not to an ambiguous mutable task.

## Journey 10: Disconnected site — **Phase 3**

A remote site may temporarily lose connection to the central control plane.

Future agents should continue executing already deployed tasks, preserve local history, and synchronise results when connectivity returns. The initial implementation need not deliver this feature, but protocols and identifiers should not make it impossible.

## Journey 11: Monitoring integration — **Phase 2**

An enterprise already uses Nagios or Prometheus.

TaskControl should not require immediate replacement. It should be able to:

- expose execution and freshness status;
- generate monitoring definitions where appropriate;
- call existing monitoring tools;
- accept references to external checks;
- preserve internal execution records;
- avoid claiming success solely because an external monitor is configured.

## Journey 12: Template and task collection — **Phase 2**

A team maintains many related scheduled tasks.

They should be able to use:

- templates with parameters;
- task collections;
- shared profiles;
- inherited calendars and switches;
- environment-specific overrides;
- bulk deployment planning;
- consistent monitoring expectations.

Templates should reduce repetition without hiding resolved values.

## Journey 13: Failure investigation — **Phase 1**

An operator sees that a task did not deliver an expected report.

The interface should answer, in order:

1. Was a trigger expected?
2. Did the scheduler trigger it?
3. Were run conditions evaluated?
4. Was it skipped, blocked, or started?
5. What effective profile was used?
6. Which command was invoked, with secrets redacted?
7. What were stdout, stderr, exit code, and duration?
8. Did retries occur?
9. Which expected outcomes passed or failed?
10. Which notifications were sent?
11. Which task and deployment revisions were active?

## Journey 14: Safe deletion — **Phase 1**

Removing a task definition must not silently leave deployed artefacts behind. TaskControl should show active deployments and require an explicit decision to retire, uninstall, archive, or preserve them.

## Journey 15: Import and adoption — **Phase 1**

A user has existing crontabs.

Import is Phase 1 scope: a cron-backed product that cannot adopt an existing estate offers
little to the operators who need it most. Import will:

- parse entries;
- identify commands, schedules, users, and environment declarations;
- create draft Task definitions;
- flag unsupported or ambiguous constructs;
- preserve original text;
- require review before adoption;
- never overwrite existing cron entries without an explicit deployment operation.

## Acceptance questions for every feature

A feature proposal should be tested against at least three journeys: personal/local use, multi-host use, and operational investigation. It should also explain how failures and unsupported platform capabilities are surfaced.

## Journey 16: Remote asynchronous submission — **Phase 2**

A remote application needs operational work performed on a managed host, and has no SSH
access, no filesystem access, and no ability to edit a crontab.

Expected flow:

1. The application `POST`s a work item naming a **registered task type**, a payload, an
   idempotency key, and optionally a not-before time.
2. TaskControl persists the item and returns an identifier and accepted status immediately.
   The caller does not wait.
3. Cron later wakes a short-lived, bounded worker.
4. The worker claims eligible items durably, processes them, records attempts and outcomes,
   and moves each to a terminal or retry-wait state.
5. The caller queries status without knowing anything about cron or the target host.

The API never accepts an arbitrary shell command. A submission API that did would be a
remote-execution service, which is not this product.

## Journey 17: Control plane unavailable at activation — **Phase 1**

Cron wakes a managed task. TaskControl's database is unreachable.

What happens is decided per task, in its definition, never by accident (ADR 0024):

- `require_control_state` — the runnable does not run; the activation is reconciled as an
  infrastructure failure once persistence returns. For work where an unrecorded run is worse
  than a missed one.
- `continue_with_local_journal` — the runnable runs, a local journal entry is written, and
  it is reconciled into central history later. For backups and cleanups, where missing the
  work is worse than temporarily missing the record.

The operator must be able to see which policy a task uses by reading its definition.
