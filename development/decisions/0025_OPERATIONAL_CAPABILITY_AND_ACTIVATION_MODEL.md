# ADR 0025: Operational Capability, Activation Policy, and Transport Independence

- Document level: **1 — Architecture**
- Lifecycle state: Canonical
- Status: Accepted
- Date: 2026-07-27
- Owners: TaskControl maintainers
- Supersedes: the "five activation sources" framing introduced during R0; refines ADR 0022
- Superseded by: None
- Related documents: `development/product/PRODUCT_DESIGN_VISION.md`, `development/product/OPERATIONAL_MODEL_AND_PRODUCT_INTENT.md`, ADR 0011, ADR 0022, ADR 0023

## Context

The R0 reconciliation established that cron owns recurring activation (ADR 0022). While
correct, it left two modelling errors that would have shaped the product badly.

**First, it put infrastructure in the domain.** The R0 documents describe TaskControl as
"cron-backed" and enumerate cron, queue, CLI, REST, and MCP as five activation *sources*.
That models the product around the components it happens to use. A future contributor
reading it would reasonably conclude that adding a transport means extending the domain.

**Second, it treated the queue as an activation source.** It is not. When a REST caller, an
MCP client, or a CLI user submits deferred work, the queue is where that request is
*persisted* until a worker claims it. The activation source is the **request**; the queue is
infrastructure serving it.

Collapsing those distinctions hides a real asymmetry. Cron does not submit work. Cron says
*"it is now time to execute this capability."* A REST call says *"somebody has requested
this work."* Those are different events with different provenance, different authorisation,
and different failure modes, and a model that calls them both "activation sources" cannot
express the difference.

There is also a naming problem. "Operational work" is used for two things: the reusable
definition of something the organisation can do, and each individual run of it. `cleanup` is
one capability, whether it is scheduled nightly, called over REST, requested through MCP,
queued by another application, or run by hand. Each of those produces a different run of the
same thing.

## Decision drivers

- The domain must be stable across transports that do not exist yet.
- Recurring and requested activation are genuinely different and must stay distinguishable.
- A reusable definition and one run of it are different objects and must be named
  differently.
- Infrastructure choices — cron, a database queue, an HTTP framework — must be replaceable
  without touching the domain.

## Considered options

### Option A — Keep the five-sources model

Simple to state. Puts four transports and one storage mechanism on the same footing as an
operating-system scheduler, models the product around its infrastructure, and grows by one
domain concept per transport.

### Option B — Capability and request, with activation split into policy and mechanism

More concepts up front. Makes the transport list a property of the adapter layer rather than
of the domain, and expresses the cron/request asymmetry directly.

## Decision

Adopt **Option B**.

### Operational Capability is the primary domain concept

> **An Operational Capability is a reusable, versioned, independently deployable definition
> of something the organisation can do.**

Backup, cleanup, market close, send report, health check, reconcile. It exists whether or not
it ever runs.

The domain model is:

```text
Operational Capability      the reusable definition
        |
Execution Request           one request that it be performed, with provenance
        |
Execution Instance          one recorded attempt to perform it
        |
Outcome                     what happened, classified honestly
```

This distinguishes the definition from the run, which the previous "operational work" framing
could not.

### Activation splits into policy and mechanism

```text
Capability
    |
Activation Policy       recurring | immediate | deferred
    |
Activation Mechanism    cron | CLI | REST | MCP | queue worker
    |
Execution
    |
Observation
```

**Activation policy** is a domain concept. It describes *how a capability becomes active* and
lives in the definition.

**Activation mechanism** is an adapter concern. It describes *what caused this particular
request* and is recorded as provenance on the request — never as a branch in the domain.

### Two kinds of activation, not five sources

| Kind | Meaning | Mechanism |
|---|---|---|
| **Recurring activation** | "It is now time to execute this capability." | cron scheduler |
| **On-demand activation** | "Somebody has requested this work." | CLI, REST, MCP, and future transports |

Recurring activation carries no requester. On-demand activation always does, and that
requester is subject to authorisation. Conflating them would lose both facts.

### The queue is infrastructure, not a source

Deferred on-demand work is **persisted in the queue** and later claimed by a worker that cron
wakes:

```text
REST | MCP | CLI  ->  submit request  ->  queue (durable)  ->  worker claims  ->  execute
```

The queue does not originate anything. The request does. A queue worker is an activation
*mechanism* for already-submitted requests, which is why it uses the same durable claim
primitive as scheduled overlap (ADR 0023) rather than a parallel one.

An immediate CLI run bypasses the queue entirely. Same capability, same execution, different
activation policy.

### The domain is transport-independent

> **The domain model SHALL remain transport-independent. MCP, REST, CLI, and future
> transports are adapters over the same application services.**

Every transport calls the same application service — conceptually
`SubmitExecutionRequest()` — and the domain neither knows nor cares which one called.

This has a direct consequence for planning: **MCP is not a roadmap feature.** It is an
adapter. It appears in the roadmap only as the work of writing an adapter, never as a
capability that changes the domain. The same is true of a future gRPC or GraphQL surface.

If adding a transport requires a domain change, the domain is wrong.

### Distribution: architecture ready, implementation single-machine

The architecture must not prevent multiple machines. Capability packages, scheduler adapters,
execution adapters, and persistence adapters are already the seams that allow it.

The implementation starts single-machine and stays there until a real requirement arrives.
Distributed coordination built before anyone needs it is coordination designed against
guesses. This is deliberate evolutionary architecture, not an oversight, and it is why
multi-host work remains a later phase.

## Rationale

Modelling around capabilities and requests keeps the domain stable while the infrastructure
underneath changes — which it will. Splitting activation into policy and mechanism captures
the one asymmetry that matters, between time arriving and a person asking, without inventing
a domain concept per transport.

The naming change earns its cost immediately: it is what allows one `cleanup` capability to
be scheduled nightly, invoked over REST, and run by hand, with each run separately recorded
against the same definition.

## Consequences

### Positive

- The domain does not grow when a transport is added.
- Requester provenance and authorisation have an obvious home on the request.
- The definition/run distinction becomes explicit, which execution history depends on.
- The queue is correctly placed as infrastructure, so it is not over-designed into a broker.

### Negative or accepted trade-offs

- Four concepts where the code currently has two. Existing names — `Task`, `TaskRevision`,
  `Execution` — do not match this vocabulary and will read as a translation layer until R1
  decides whether to rename.
- "Capability" and "task" will coexist in conversation for a while.
- Activation policy adds a field to the definition that most users will never change.

### Risks and mitigations

- Risk: a transport adapter grows domain logic because it is convenient — mitigation: the
  architecture test already forbids business rules in transport layers; the application
  service is the only entry point.
- Risk: renaming churns working code for a documentation change — mitigation: R1 decides on
  evidence, and mapping the existing names is acceptable if renaming is not worth it.

## Implementation constraints

- No domain module may branch on activation mechanism. Mechanism is recorded, not consulted.
- Every transport calls the same application service; none owns its own execution path.
- Activation policy belongs to the capability definition and is therefore versioned.
- The queue stores and claims; it never decides what should run.
- Nothing may assume single-machine deployment in a way that requires a domain change later.

### Mapping to the current code

The implementation predates this vocabulary. Until R1 decides on renaming:

| This ADR | Current code |
|---|---|
| Operational Capability | `Task` plus its `TaskRevision` |
| Execution Request | `RunRequest` |
| Execution Instance | `Execution` |
| Activation mechanism | `TriggerSource` |
| Outcome | `ExecutionOutcome` |

The concepts already exist. The names are from the earlier direction.

## Validation

A reviewer can confirm: no domain module imports or branches on a transport; adding a
transport requires only an adapter and a composition change; a capability's definition states
its activation policy; and an execution record shows which mechanism activated it.

## Migration and compatibility

No production data exists. R1 decides on renaming with evidence; this ADR does not require it.

## Future evolution and review triggers

Reconsider if a genuine third kind of activation appears that is neither time-arriving nor
requester-driven — an event-driven source reacting to external state is the likely candidate,
and it would deserve its own analysis rather than being forced into "on-demand".

## Rejected alternatives

Option A was rejected because it models the product around its infrastructure, which
guarantees the domain changes every time the infrastructure does.
