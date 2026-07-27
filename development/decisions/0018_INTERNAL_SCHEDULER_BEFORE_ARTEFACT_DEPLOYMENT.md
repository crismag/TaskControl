# ADR 0018: Internal Scheduler Before Scheduler-Artefact Deployment

- Document level: **1 — Architecture**
- Lifecycle state: Canonical
- Status: **Superseded** — retained for decision history; do not implement from it
- Date: 2026-07-26
- Owners: TaskControl maintainers
- Supersedes: Wave ordering in `development/archive/05_DELIVERY_ROADMAP.md`; first-release scope in `development/archive/06_FULL_APPLICATION_BLUEPRINT.md`
- Superseded by: **ADR 0022 (Cron Owns Recurring Activation)**
- Related documents: `development/product/PRODUCT_SCOPE.md`, `development/product/PRODUCT_ROADMAP.md`, `development/domain/05_TARGETS_INVENTORY_DEPLOYMENTS_AND_DRIFT.md`, ADR 0007, ADR 0010

> **Superseded by ADR 0022 on 2026-07-27.** This decision put an internal scheduler in
> Phase 1 and deferred cron-artefact generation to Phase 2. The reasoning below — prove
> execution semantics before compiling them into a target TaskControl does not own — remains
> sound as *engineering sequencing*, but it was applied to a question it could not settle:
> whether TaskControl is a scheduler or manages one. Cron now owns recurring activation.
>
> Wave 3 was built under this decision and is retained. Nothing here is rewritten to pretend
> otherwise; read ADR 0022 for the current direction and the reasons for the change.

## Context

The repository contains two different theses about what TaskControl fundamentally does, introduced in different eras and never reconciled.

**The generation thesis** (original vision, product philosophy, delivery roadmap, application blueprint): the user declares intent and TaskControl compiles it into native scheduler artefacts — crontab entries, systemd timers, later Kubernetes CronJobs — which the host executes. TaskControl's job is authoring, generation, deployment, and drift detection. Wave 4 of the retired roadmap was cron deployment; the retired blueprint's core vertical slice ran through artefact generation and `plan`/`apply`.

**The orchestration thesis** (PR #7 product package): TaskControl is a standalone application that schedules and executes work itself, through its own runtime, observed through its own API and UI. Across the seven product documents, "cron" appears twice as a passing example and "deployment" appears once, in Phase 2.

The Phase 1 scope in `PRODUCT_SCOPE.md` contains no artefact generation, no target inventory, and no cron adapter — yet ADR 0010 (plan-apply-verify) is binding, `domain/05` specifies targets and drift in 368 lines, and the retired roadmap put cron deployment before the API. An implementer cannot satisfy both readings, and the conflict is invisible because each document is internally consistent.

## Decision drivers

- The product must deliver standalone value without a host scheduler (`PRODUCT_VISION.md`, principle 1).
- Execution semantics must be proven before they are compiled into a target that TaskControl does not control.
- Generated-artefact deployment is the harder and more dangerous capability: it writes to user crontabs and must never damage unmanaged content.
- Deferring a capability must not remove its extension points (ADR 0011, engineering law 9).
- Two theses in one repository produce contradictory implementations.

## Considered options

### Option A — Generation first

Build cron rendering, plan/apply, and drift detection before the API and UI, as the retired roadmap specified.

Strengths: matches the original differentiators; delivers the "replace my crontab" story early. Weaknesses: the riskiest subsystem is built against unproven execution semantics; the product has no usable interface until later; contradicts the accepted Phase 1 scope.

### Option B — Internal execution first, generation as a later delivery mode

Build TaskControl's own scheduler, runtime, and observation surfaces first. Add artefact generation and deployment in Phase 2 as an additional way to deliver an already-proven task.

Strengths: standalone value immediately; deployment is built on settled execution semantics; matches the accepted product scope. Weaknesses: defers the original headline differentiator; the internal scheduler is new work the generation thesis would not have needed.

### Option C — Both in Phase 1

Rejected on scope grounds: it reproduces the "attempt everything" instruction that the retired prompts contained.

## Decision

Adopt **Option B**, and record explicitly that both theses are correct in sequence rather than in competition.

**Phase 1 — TaskControl executes.** An internal scheduler evaluates schedules and eligibility inside the application and invokes the TaskControl runtime directly. There is one target, `local`, and no generated scheduler artefacts. The user installs TaskControl, defines a task, and TaskControl runs it.

**Phase 2 — TaskControl also generates.** Scheduler adapters compile a task revision into native artefacts; the plan-apply-verify model of ADR 0010 governs their installation; drift detection compares desired and observed state. Cron is the first adapter, systemd the second. The internal scheduler remains available and is the default.

The scheduler adapter port (ADR 0007) and the deployment port are defined in Phase 1 and implemented with the trivial internal cases. `domain/05` and ADR 0010 remain binding architecture; their **implementation** is Phase 2. Nothing in Phase 1 may foreclose them: task revisions stay immutable and content-addressable, targets stay a modelled concept rather than an assumption of `localhost`, and the runtime entry point stays invocable from an external scheduler.

Consequently `taskctl run --deployment-id ...` — the retired architecture's cron invocation line — remains the intended Phase 2 shape, and the Phase 1 runtime is written so that an external trigger can enter it unchanged.

## Rationale

The dangerous half of the product is the half that writes to a user's crontab. Building it against execution semantics that have not yet run in anger is how a scheduled-task tool destroys someone's estate. Option B lets outcome classification, retry, timeout, locking, and expectation evaluation settle under direct control, then exports them. It is also the only option consistent with the accepted Phase 1 scope, which is Level 0 and outranks the retired roadmap.

## Consequences

### Positive

- Phase 1 delivers a product a user can install and rely on.
- Deployment is built on proven semantics.
- The two theses stop competing; the product statement becomes "TaskControl runs your work, and can later hand it to a native scheduler without redefining it".

### Negative or accepted trade-offs

- The original "managed crontab" differentiator arrives in Phase 2.
- TaskControl must run as a persistent process to schedule work in Phase 1; a purely stateless installation is not a Phase 1 deliverable.
- An internal scheduler is work the generation thesis would have avoided.

### Risks and mitigations

- Risk: the internal scheduler misses triggers while the process is down — mitigation: misfire policy and restart catch-up are explicit Phase 1 requirements, not later fixes.
- Risk: deferred ports rot — mitigation: the scheduler and deployment ports carry a real `local` implementation and contract tests from Wave 5.
- Risk: users expecting a cron manager are disappointed — mitigation: `PRODUCT_SCOPE.md` and the README state the Phase 1 boundary plainly.

## Implementation constraints

- The runtime entry point must be invocable by the internal scheduler, the API, the CLI, and a future external scheduler through the same path.
- `Target` is a modelled entity in Phase 1 even though only `local` exists.
- No Phase 1 code may write to a user crontab or any host scheduler configuration.
- Schedule evaluation and eligibility evaluation stay separable so a Phase 2 adapter can render a coarse trigger plus a runtime guard.

## Validation

A reviewer verifies that no Phase 1 module writes host scheduler configuration, that the scheduler and deployment ports exist with `local` implementations and contract tests, and that the runtime is entered identically from all four callers.

## Migration and compatibility

No code exists. Phase 2 adds adapters behind existing ports; no Phase 1 domain change is anticipated.

## Future evolution and review triggers

Reconsider the ordering if a concrete user requirement demands managed crontab output before an operable Phase 1 product exists, or if running a persistent TaskControl process proves unacceptable to the target users.

## Rejected alternatives

Option A was rejected because it builds the destructive subsystem first and contradicts the accepted Level 0 scope. Option C was rejected as unbounded.
