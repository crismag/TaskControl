# Use Cases and User Journeys

## Purpose

This document grounds TaskControl in real operational journeys. Claude, Codex, and human contributors should use these examples to test whether proposed abstractions are useful rather than merely elegant.

## Journey 1: Personal scheduled task

A developer wants a Python report to run every weekday at 08:00 on a Linux workstation.

Expected flow:

1. Create a Task named `daily-project-report`.
2. Select the Python execution adapter.
3. Select the script and arguments.
4. Define a weekday schedule at 08:00 in the local time zone.
5. Preview the generated execution package and cron artefact.
6. Run a validation and test execution.
7. Install the deployment locally.
8. View execution history and logs.
9. Disable, update, rollback, or remove the deployment.

Minimum value: TaskControl must make this easier and safer than hand-editing crontab while retaining transparency.

## Journey 2: Existing shell script with profile guards

An operations engineer has an established shell script that currently sources a shared profile and calls helper functions such as `ifholiday` before doing work.

Expected flow:

1. Register the existing script without rewriting it.
2. Model environment variables as a reusable Runtime Profile.
3. Model the holiday check as a Calendar-backed Run Condition.
4. Preview a generated wrapper that resolves the profile, evaluates conditions, records the decision, and invokes the original script.
5. Preserve the original script as the work implementation while moving cross-cutting operational behaviour into TaskControl.
6. Record `SKIPPED_CALENDAR_CLOSED` explicitly rather than relying on a silent early exit.

## Journey 3: Production file delivery

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

## Journey 4: Multi-host deployment

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

## Journey 5: Mixed scheduler platforms

An organisation needs comparable operations on Linux cron, Linux systemd, Kubernetes, and Windows.

The Task definition should remain stable. Platform-specific Scheduler Adapters generate native artefacts. Unsupported semantics must be reported during planning rather than silently approximated.

Example: a scheduler that cannot express a complex calendar condition should generate a frequent trigger plus a TaskControl runtime guard rather than dropping the condition.

## Journey 6: Exchange calendar operation

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

## Journey 7: Maintenance switch

An operator needs to stop a family of tasks without editing each schedule.

TaskControl should allow a Runtime Switch or inherited Run Condition at an application, environment, host group, or task level. Every skipped execution must identify the switch, its resolved value, origin, and reason.

## Journey 8: Dependency-aware execution

A downstream task should run only when a required upstream operation has completed successfully and its output remains fresh.

The first version may support simple dependency checks without becoming a full DAG workflow engine. The design must distinguish:

- scheduler trigger;
- permission to start;
- dependency state;
- execution ordering;
- expected outcomes.

Avoid turning TaskControl into a general-purpose data pipeline orchestrator unless later product decisions explicitly expand the scope.

## Journey 9: Approval-controlled production deployment

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

## Journey 10: Disconnected site

A remote site may temporarily lose connection to the central control plane.

Future agents should continue executing already deployed tasks, preserve local history, and synchronise results when connectivity returns. The initial implementation need not deliver this feature, but protocols and identifiers should not make it impossible.

## Journey 11: Monitoring integration

An enterprise already uses Nagios or Prometheus.

TaskControl should not require immediate replacement. It should be able to:

- expose execution and freshness status;
- generate monitoring definitions where appropriate;
- call existing monitoring tools;
- accept references to external checks;
- preserve internal execution records;
- avoid claiming success solely because an external monitor is configured.

## Journey 12: Template and task collection

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

## Journey 13: Failure investigation

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

## Journey 14: Safe deletion

Removing a task definition must not silently leave deployed artefacts behind. TaskControl should show active deployments and require an explicit decision to retire, uninstall, archive, or preserve them.

## Journey 15: Import and adoption

A user has existing crontabs.

A future import feature may:

- parse entries;
- identify commands, schedules, users, and environment declarations;
- create draft Task definitions;
- flag unsupported or ambiguous constructs;
- preserve original text;
- require review before adoption;
- never overwrite existing cron entries without an explicit deployment operation.

## Acceptance questions for every feature

A feature proposal should be tested against at least three journeys: personal/local use, multi-host use, and operational investigation. It should also explain how failures and unsupported platform capabilities are surfaced.