# ADR 0022: Cron Owns Recurring Activation

- Document level: **1 — Architecture**
- Lifecycle state: Canonical
- Status: Accepted
- Date: 2026-07-27
- Owners: TaskControl maintainers
- Supersedes: ADR 0018 (Internal Scheduler Before Scheduler-Artefact Deployment)
- Superseded by: None
- Related documents: `development/product/PRODUCT_VISION.md`, `development/product/PRODUCT_SCOPE.md`, `development/architecture/ARCHITECTURE_OVERVIEW.md`, `development/10_IMPLEMENTATION_BLUEPRINT.md`, ADR 0007, ADR 0010, ADR 0023, ADR 0024

## Context

ADR 0018 decided that TaskControl would schedule and run work itself in Phase 1 through an
internal scheduler, deferring cron-artefact generation to Phase 2. It was accepted on
2026-07-27 and Wave 3 was built under it.

The reasoning was about build order: prove execution semantics under direct control before
compiling them into a target TaskControl does not own. That reasoning still holds *as
engineering sequencing*. It was applied to the wrong question.

An internal scheduler is not an implementation detail that can be sequenced ahead of cron
management. It determines what the product is. A system whose recurring jobs stop when its
own process stops is a scheduler — one competing with cron, systemd timers, and every
platform scheduler an operator already runs. A system that manages cron is something else
entirely: it adds authoring, knowledge, governance, and observability around a mechanism the
operator already trusts and already depends on.

The product intent is the second. Recording it late does not make the earlier decision
dishonest; it makes it superseded. Wave 3 was built correctly under the direction that was
canonical at the time, and this ADR does not rewrite that history.

### What the earlier decision would have cost

Left in place, ADR 0018 commits TaskControl to:

- an always-on process that recurring jobs depend on, which is a new single point of failure
  in an estate that previously had none;
- competing with cron on reliability, where cron has decades of operational trust;
- treating managed crontab generation — the capability operators actually asked for — as
  distant Phase 2 scope;
- an availability story where a control-plane outage silently stops scheduled work.

## Decision drivers

- Recurring work must keep running when the TaskControl API and web UI are down.
- Operators already trust cron; the product should add to it rather than replace it.
- Users should not need cron syntax for ordinary authoring — that is TaskControl's job.
- Short-lived, cron-invoked processes must be a first-class execution shape.
- Work already built must be reused where it genuinely fits, not discarded for tidiness.

## Considered options

### Option A — Keep the internal scheduler as the Phase 1 engine

Preserves the existing plan and Wave 3's framing. Retains the availability problem, keeps
cron management distant, and continues building a product the intent does not describe.

### Option B — Cron owns recurring activation; TaskControl manages cron

Reverses the sequencing decision. Requires the cron adapter earlier than planned and
demotes the runtime from product centre to supporting service. Recurring jobs survive
control-plane downtime because cron, not TaskControl, wakes them.

### Option C — Both, with cron optional

Two activation paths, two failure models, two sets of semantics to keep aligned. The
ambiguity would surface as "did this run, and which mechanism should have run it?" — exactly
the question the product exists to answer.

## Decision

Adopt **Option B**.

**Cron owns durable time-based activation.** TaskControl owns everything around it: task
definitions and revisions, human-friendly schedule authoring, managed cron artefact
generation and lifecycle, drop-in discovery, operational knowledge, remote API contracts,
durable queued work, execution services, outcomes, and audit.

### Consequences for the process model

TaskControl must not require one immortal process for recurring activation. Supported
process shapes are all short-lived except the optional control plane:

| Shape | Lifetime | Purpose |
|---|---|---|
| Control plane | long-running, optional | Web UI and API for management and inspection |
| Cron management command | short-lived | plan, apply, verify, import, adopt |
| Scheduled task wrapper | short-lived | one activation of one managed task |
| Queue worker | short-lived, bounded | claim and process eligible work items |
| Drop-in reconciler | short-lived | discovery and registration |

A deployment may run the API continuously. Recurring jobs must not depend on it.

### Consequences for Wave 3

The execution runtime built in Wave 3 is **retained and repositioned**. It remains the way
one bounded execution is performed, classified, and recorded — invoked by a cron-generated
wrapper, a queue worker, or an explicit run-now operation. It is no longer the product
centre, and `taskctl run` is no longer the primary scheduled-job workflow.

Two Wave 3 assumptions are explicitly withdrawn:

1. That an internal scheduler would activate recurring work (this ADR).
2. That process-local overlap locking is sufficient for scheduled activation. Under cron,
   each activation is a separate process, so an in-memory lock protects nothing across
   activations. See **ADR 0023**.

A third question that ADR 0018 never had to ask now becomes unavoidable: what a cron-woken
wrapper does when it cannot reach TaskControl's persistence. See **ADR 0024**.

### Scheduler abstraction retained

ADR 0007's scheduler port stands, with its purpose corrected. It exists to **manage external
scheduler targets**, not to abstract over an internal scheduler. Cron is the first
production adapter; systemd timers and platform schedulers follow. Nothing in the domain may
assume a particular scheduler, and nothing may assume TaskControl is one.

### Deployment model retained

ADR 0010's plan-apply-verify model becomes immediate rather than deferred. Managed cron
artefacts are planned, applied, and verified by read-back, and unmanaged crontab content is
never overwritten.

## Rationale

The availability argument decides it. An operator adopting TaskControl for a nightly backup
must not thereby make that backup depend on a web application staying up. Cron already
provides durable activation with operational trust that TaskControl cannot earn quickly and
has no reason to try to. The product's value is in the layer above — the layer that is
currently missing everywhere.

Reversing this late costs one wave's framing and no working code. Reversing it after
building the scheduler, the API, and the UI on top of it would cost all three.

## Consequences

### Positive

- Recurring work survives any TaskControl outage.
- The capability operators asked for — managed cron — becomes early scope.
- No competition with a mechanism that already works.
- The product boundary is sharp: cron activates, TaskControl governs.

### Negative or accepted trade-offs

- Sub-minute scheduling is not available through cron. A task needing it must use a
  different activation mechanism, which is a deliberate limitation rather than an oversight.
- TaskControl inherits cron's semantics, including its misfire behaviour and its lack of a
  native catch-up concept.
- Wave 3 documentation and naming carry a scheduler-first framing that must be corrected;
  ADR 0023 and a compatibility review handle the substance.
- Roadmap sequencing changes: the old Wave 4 (expectations) is stopped in favour of proving
  cron-backed user value first.

### Risks and mitigations

- Risk: a managed cron write damages unmanaged entries — mitigation: managed blocks with
  stable identifiers, plan before apply, read-back verification, fail closed on ambiguous
  block identity, and a reversible rollback path.
- Risk: "cron-backed" is read as "cron is a legacy adapter" — mitigation: cron is named as
  the dependable production substrate in every Level 0 document, not as a compatibility
  layer.
- Risk: an internal scheduler returns under another name — mitigation: no polling loop, no
  in-memory timer, and no always-on activation process is permitted; the blueprint states
  this as an architecture requirement for every wave.

## Implementation constraints

- No component may implement a recurring in-memory timer or polling loop for activation.
- Domain and application layers depend on scheduler-**management** ports, never on a cron
  library.
- Cron rendering, installation, import, and verification live in adapters.
- Execution services stay bounded and short-lived, callable from a process that exits.
- A user must be able to author an ordinary schedule without writing a cron expression.
- Unmanaged cron content is never overwritten.

## Validation

A reviewer can confirm: no active document describes an internal scheduler as the Phase 1
activation engine; no source module runs a recurring timer; a scheduled task activates with
the API process stopped; and applying a managed artefact leaves unmanaged entries byte
identical.

## Migration and compatibility

No production deployment exists, so no data or estate migrates. Within the repository:
Waves 0–3 are marked complete under the previous direction and retained pending a
compatibility review (blueprint R1). Wave 3 code is not rewritten by the reconciliation that
introduces this ADR.

## Future evolution and review triggers

Reconsider if a concrete requirement needs sub-minute activation that cron cannot express,
or if a target platform provides no cron-equivalent, in which case an additional scheduler
adapter — not an internal scheduler — is the answer.

## Rejected alternatives

Option A was rejected because it makes recurring work depend on TaskControl's own
availability, which no operator asked for and which cron already solves. Option C was
rejected because two activation paths produce two failure models and an unanswerable
question about which one should have run.
