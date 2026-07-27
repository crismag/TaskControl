> **STATUS: SUPERSEDED** — replaced by `development/domain/` (the domain handbook) and ADR 0016.
>
> Retained for historical reasoning. **Do not use for new implementation.**
>
> Superseded: 2026-07-26. Reason: The outcome taxonomy here was one of three incompatible versions; ADR 0016 is now the sole authority. Aggregate definitions are superseded by the eleven-file domain handbook.

---

# Domain Model

## Aggregate roots

### TaskDefinition
Represents reusable operational intent independent of a host.

Suggested fields:
- id, name, description
- version and lifecycle state
- executor specification
- trigger references
- run-condition references
- profile references
- runtime controls
- expectations
- labels, owner, provenance

### ScheduleDefinition
Represents when a task is considered for execution.

Types:
- cron expression
- interval
- named calendar event
- manual/API trigger
- future event adapters

A schedule must expose timezone, next-run preview, misfire behaviour, and enabled state.

### CalendarDefinition
Represents business or operational dates and sessions.

Supports:
- timezone
- working weekdays
- holidays and exceptional closures
- early-close or special-session metadata
- include/exclude dates
- named sessions or events
- source and version metadata

### ProfileDefinition
Represents layered execution configuration.

Contains non-secret variables, path settings, adapter configuration, references to secrets, calendar defaults, and runtime switches. Profile composition order must be deterministic and provenance visible.

### RunConditionDefinition
Represents a reusable pre-execution guard.

Initial condition types:
- calendar day is eligible
- not a holiday
- runtime switch enabled
- allowed environment
- host role or deployment label match
- required file or directory exists
- process or endpoint health check
- overlap lock available

Each evaluation returns a structured decision and reason.

### Deployment
Binds a task version to a target, scheduler, identity, profiles, and overrides.

Contains:
- logical task/version
- target host or local target
- execution identity
- scheduler adapter
- resolved deployment configuration hash
- desired state and observed state
- deployment status and timestamps

### ExecutionAttempt
Represents every trigger evaluation, including skips.

Contains:
- execution id
- deployment id and task version
- trigger source and scheduled time
- start/end timestamps
- resolved profile/configuration fingerprint
- condition decisions
- outcome and reason code
- exit code, timeout, signal
- log and artefact references
- parent/correlation identifiers

### MonitoringExpectation
Defines observable evidence of success or required system state.

Initial types:
- command exit classification
- file existence or freshness
- process running
- endpoint healthy
- output pattern
- execution completed by deadline

### TaskCollection
Groups ordered or parallel task steps under a shared trigger/profile/runtime policy. Initial implementation may support sequential collections only, but the schema must allow explicit ordering and failure behaviour.

## Outcome taxonomy

At minimum:
- `SUCCEEDED`
- `FAILED`
- `SKIPPED`
- `BLOCKED`
- `TIMED_OUT`
- `CANCELLED`
- `SUPPRESSED`
- `UNKNOWN`

Skip reasons should be machine-readable, such as `HOLIDAY`, `SWITCH_DISABLED`, `ENVIRONMENT_NOT_ALLOWED`, `OVERLAP_PREVENTED`, or `MANUAL_HOLD`.

## Identifier strategy

Use opaque stable identifiers with readable names as mutable labels. Avoid encoding hierarchy into IDs. All externally shared records should include tenant/domain fields later without changing primary object semantics.

## Versioning

Task definitions, profiles, calendars, and generated bundles must be versionable. Deployments reference immutable versions or content hashes. Editing a definition creates a new version rather than silently changing historical execution meaning.

## Configuration resolution

Recommended precedence, from lowest to highest:
1. system defaults
2. organisation or installation defaults
3. environment profile
4. platform profile
5. application profile
6. host/group profile
7. deployment overrides
8. task-run overrides permitted by policy

The resolved view must show value, source layer, and whether the value is secret.

## Invariants

- A task definition is not a deployment.
- A trigger does not guarantee execution.
- A skipped execution is recorded.
- Secrets are referenced, not embedded.
- Historical execution records retain the effective task/profile version.
- Generated artefacts can be reproduced from stored definitions and adapter versions.
