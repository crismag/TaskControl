# Cron and Drop-In Model

- Status: Proposed

## Design principle

Cron is the scheduling substrate. TaskControl is the management, knowledge, API, and optional execution-support layer around it.

Users should normally think in terms of tasks and schedules, not cron syntax or runner commands.

## Human-friendly schedule model

TaskControl should support common schedule forms such as:

- every 5 minutes;
- hourly;
- daily at a selected local time;
- weekdays at a selected time;
- selected days of the week;
- monthly on a selected day;
- advanced cron expression for expert users.

The UI and API preserve the user's schedule intent while the cron adapter produces the target expression. Time zone and daylight-saving behaviour must be explicit.

## Managed cron artefacts

TaskControl-generated entries must be recognisable and reversible. They should include stable identifiers and should not overwrite unrelated user entries.

A managed block may resemble:

```cron
# BEGIN TASKCONTROL managed-id=nightly-report revision=12
0 2 * * * /opt/taskcontrol/jobs/nightly-report/run
# END TASKCONTROL managed-id=nightly-report
```

The exact format requires an ADR. The important requirements are:

- deterministic rendering;
- safe escaping;
- stable identity independent of display name;
- plan before apply;
- atomic update where the host supports it;
- read-back verification;
- preservation and reporting of unmanaged entries;
- rollback or recovery from interrupted updates.

## Drop-in package

A first-class drop-in should be self-describing:

```text
nightly-report/
    task.yaml
    run.sh
    README.md          # optional
    schemas/           # optional payload/result schemas
```

A minimal manifest should describe:

- task identifier and display name;
- purpose and owner;
- runnable entry point and type;
- recurring schedule or queue-handler eligibility;
- working directory;
- configuration and secret references;
- timeout, overlap, and retry preferences;
- expected outputs or evidence;
- optional source repository and runbook.

## Discovery lifecycle

```text
Unseen -> Discovered -> Validated -> Registered -> Deployed -> Active
                           |              |
                           v              v
                        Rejected       Disabled/Retired
```

Discovery alone must not automatically grant permission to execute. Deployment may require policy checks or approval.

## Two cron integration patterns

### Pattern A — one managed entry per scheduled task

Best for independently scheduled recurring work. Cron invokes a stable local wrapper associated with the task revision or current deployment.

### Pattern B — stable cron dispatcher

Best for queue polling, drop-in reconciliation, or bounded batch pickup. A small stable cron entry invokes a worker that claims persisted eligible work.

Pattern B must not hide a custom minute-by-minute scheduler inside TaskControl. Cron supplies wake-up timing; durable queue eligibility determines what the bounded worker processes.

## Import and adoption

Existing cron entries should be classified as:

- managed and matching;
- managed but drifted;
- unmanaged and adoptable;
- unmanaged and unsupported;
- invalid or broken;
- duplicate or conflicting.

Adoption should create a proposed TaskControl definition and preserve the original entry until the user explicitly applies the migration.

## Run-now behaviour

TaskControl may offer manual run-now for testing, recovery, or operations. It is not the normal mechanism for recurring work and should not be used to justify an internal replacement scheduler.

## Failure isolation

Already-installed cron entries must remain present and executable when the web/API process is unavailable. The generated execution boundary should depend only on local assets required for the task.

Where a wrapper provides TaskControl telemetry, failure to contact an optional remote observation service should not automatically suppress the underlying runnable. Cases where persistence or locking is mandatory must be declared by task policy.
