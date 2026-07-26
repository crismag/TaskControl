# Schedules, Triggers, Calendars, and Run Conditions

- Document level: **1 — Architecture**
- Lifecycle state: Canonical

## Purpose

This domain determines when a task is nominally due and whether a particular trigger occurrence is permitted to become an execution.

The critical distinction is:

> A schedule proposes a trigger. Conditions and policy decide eligibility. Execution is a later step.

## Schedule

A Schedule is a reusable temporal rule.

### Attributes

- `schedule_id`.
- Name and description.
- Schedule type.
- Expression or structured rule.
- IANA time zone.
- Effective start and optional end.
- Enabled state.
- Misfire policy.
- Jitter policy, when supported.
- Created and modified audit metadata.

### Supported initial schedule types

- Cron expression.
- Structured interval.
- One-time date/time.
- Manual-only, represented by absence of automatic schedule rather than a fake cron expression.

### Future schedule types

- Business-day schedule.
- Calendar session schedule.
- Event-driven schedule.
- Dependency-completion schedule.
- External scheduler ownership.

### Time zone rules

- Every schedule must have an explicit IANA time zone.
- Server-local time must not be an implicit domain default.
- Stored trigger timestamps use UTC plus original schedule-time metadata.
- Daylight-saving gaps and overlaps require explicit deterministic handling.

Recommended DST policies:

- Missing local time: skip or run at next valid instant.
- Repeated local time: run once or twice.

The selected policy must be stored with the schedule and visible in preview.

### Misfire policy

A misfire occurs when a due trigger was not processed on time.

Initial policies:

- Ignore: do not create a replacement trigger.
- FireOnceNow: create one catch-up trigger.
- FireAllWithinLimit: future capability requiring a bounded window.

Never silently infer catch-up behaviour.

## Trigger

A Trigger is a concrete request or occurrence that can initiate eligibility evaluation.

### Trigger types

- Scheduled.
- Manual.
- API.
- Retry.
- Replay.
- Deployment validation.
- Event, future.

### Attributes

- `trigger_id`.
- Trigger type.
- Task and revision reference.
- Nominal due time.
- Actual received time.
- Time zone and local-time representation when scheduled.
- Requesting principal for manual/API triggers.
- Parent execution or attempt for retry/replay.
- Idempotency key.
- Input parameters.
- Eligibility status.
- Eligibility decision evidence.

### Idempotency

Scheduled trigger identity should be derivable from task binding, revision, schedule, target, and nominal due time. Reprocessing the same occurrence must not create duplicate executions unless an explicit replay is requested.

Manual/API triggers should accept an idempotency key.

## Trigger eligibility

A trigger passes through these stages:

1. Validate referenced task and revision.
2. Validate task lifecycle permits the trigger type.
3. Resolve target.
4. Resolve profiles and non-secret metadata.
5. Evaluate schedule effective window if applicable.
6. Evaluate calendars and run conditions.
7. Evaluate overlap and concurrency policy.
8. Evaluate approval requirements.
9. Produce one of: eligible, denied, skipped, pending approval, or evaluation error.

Eligibility must produce a structured explanation, not only a boolean.

## Calendar

A Calendar represents business dates, open/closed status, holidays, sessions, and exceptions.

### Calendar types

- Holiday calendar.
- Business-day calendar.
- Exchange or market calendar.
- Maintenance calendar.
- Custom inclusion/exclusion calendar.

### Attributes

- `calendar_id`.
- Name and scope.
- Time zone.
- Calendar type.
- Version.
- Source type: managed, imported, external provider.
- Effective date range.
- Default day classification.
- Entries and exceptions.
- Last refresh and source metadata.

### Calendar entry

An entry may specify:

- Date.
- Classification: open, closed, holiday, partial, maintenance, exceptional.
- Named session windows.
- Business date override.
- Reason and source.

### Calendar versioning

Calendar changes can alter historical eligibility. Therefore executions and trigger decisions should record the calendar version or digest used during evaluation.

### External calendar sources

Imported calendars must retain:

- Source identifier.
- Retrieval timestamp.
- Effective version.
- Validation status.
- Last successful refresh.

A failed refresh must not silently erase the last valid calendar. Staleness policy must determine whether evaluation continues, warns, or blocks.

## RunCondition

A RunCondition is a deterministic pre-execution predicate.

### Result model

Every evaluation returns:

- `decision`: allow, deny, error, or not_applicable.
- `reason_code`.
- Human-readable reason.
- Evidence metadata.
- Evaluator version.
- Evaluation time.
- Redacted inputs or references.

### Initial condition types

- Calendar day classification.
- Weekday or weekend.
- Date range.
- Time window.
- Environment match.
- Target label match.
- File exists or does not exist.
- Dependency execution result.
- Runtime switch or feature flag.
- Manual enable/disable gate.

Conditions involving target state must execute through a defined evaluator boundary and must have timeout/error semantics.

### Combination model

Conditions may be combined using explicit groups:

- All: every condition must allow.
- Any: at least one condition must allow.
- None: no condition may allow.

Avoid arbitrary executable expressions in the initial product. Structured condition trees are safer, auditable, and portable.

### Short-circuiting

Short-circuiting may improve efficiency, but the system should offer an explain mode that evaluates enough conditions to provide a useful complete eligibility report.

### Deny versus error

- Deny means the condition evaluated successfully and execution is not permitted.
- Error means eligibility could not be determined.

Error handling must be explicit. Default behaviour should fail closed for production execution unless a documented policy chooses fail open.

## Skip semantics

A scheduled occurrence denied by a routine condition should produce a Skip record or a terminal trigger decision with:

- Task revision.
- Target.
- Nominal due time.
- Condition responsible.
- Reason.
- Calendar/profile versions used.

Examples:

- Holiday.
- Exchange closed.
- Maintenance window.
- Runtime switch disabled.
- Overlap forbidden.

A skip is neither process success nor process failure.

## Preview and explanation

The application must support schedule preview for a requested range, showing:

- Nominal due time.
- Local and UTC time.
- Calendar classifications.
- Condition decision.
- Expected eligibility.
- DST or exception notes.

It must also support `explain eligibility` for one task, target, and instant.

## Persistence guidance

Store Schedule, Calendar, and RunCondition definitions separately. Trigger occurrences and eligibility decisions are durable operational records.

For each decision preserve:

- Definition identifiers and versions.
- Evaluator versions.
- Input references.
- Decision and reason codes.
- Correlation identifier.

## API guidance

Recommended resources:

- `/schedules`
- `/calendars`
- `/conditions`
- `/tasks/{task_id}/schedule-preview`
- `/tasks/{task_id}/eligibility`
- `/triggers`
- `/triggers/{trigger_id}`

Calendar import and refresh should use explicit commands.

## CLI guidance

```text
taskctl schedule preview <task> --from ... --to ...
taskctl task explain-eligibility <task> --target local --at ...
taskctl calendar import <file>
taskctl calendar show <calendar> --date ...
taskctl trigger replay <trigger>
```

## UI guidance

The schedule editor should offer structured forms and an advanced cron mode. Preview must be visible before publication.

The eligibility view should explain each decision in order, including inherited profiles, calendar versions, condition outcomes, overlap status, and approvals.

## Validation rules

- Time zone is required and valid.
- Effective end is after start.
- Cron or interval expression is valid.
- Condition graphs are acyclic.
- Calendar references exist and are compatible with date range/time zone.
- Trigger parameters conform to the revision schema.
- Scheduled trigger idempotency is enforced.
- Errors cannot be silently converted to allow.
- Replays must be distinguishable from original triggers.

## Future extensions

- Rich exchange sessions.
- Dependency DAGs.
- Event subscriptions.
- Distributed leader election for due-trigger generation.
- Regional calendar replicas.
- Policy-as-code condition plugins.
- Forecasting and missed-run analysis.
