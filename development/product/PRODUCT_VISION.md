# Product Vision

- Document level: **0 — Identity**
- Lifecycle state: Canonical
- Governs: everything below Level 0. When another document disagrees with this one, this one is right.
- Related: ADR 0022 (cron owns recurring activation), ADR 0025 (capability and activation model)

## Mission

Make operational work easy to define, dependable to activate, simple to observe, and safe to
govern — without replacing the scheduler an operator already trusts.

## North star

> **TaskControl is an operational automation platform. It manages the full lifecycle of
> operational capabilities — definition, deployment, activation, execution, observation,
> governance, history, and audit — so that people, applications, and AI systems can define
> operational work once and activate it through any supported mechanism.**
>
> **It automates the work of production engineers, not just the execution of scripts.**

Cron remains the operating-system scheduler for recurring activation. TaskControl does not
replace it; it automates everything experienced production engineers have historically built
around it.

## The problem

Operational automation is scattered across crontabs, shell scripts, ad hoc services, drop
folders, databases, and undocumented server conventions. The commands often keep running for
years. What gets lost is everything around them:

- why a task exists, and who owns it;
- where its runnable lives, and which hosts carry it;
- how it is scheduled, and whether the installed schedule still matches the intent;
- what submitted asynchronous work is waiting, running, complete, or failed;
- whether a failure was retried or needs a human;
- what changed, when, and who changed it.

Cron does its job well. The knowledge and control *around* cron is what is missing, and that
is the gap TaskControl fills.

## The primary concept

> An **Operational Capability** is a reusable, versioned, independently deployable definition
> of something the organisation can do: backup, cleanup, market close, send report, health
> check, reconcile.

The same capability may be scheduled nightly, called over REST, requested through MCP, queued
by another application, or run by hand. It is one capability; each run is an **execution
instance** of it (ADR 0025).

```text
Operational Capability  ->  Execution Request  ->  Execution Instance  ->  Outcome
```

TaskControl is modelled around capabilities and requests, **not** around the infrastructure
that happens to serve them. Cron, the queue, REST, and MCP are activation mechanisms and
adapters — never the centre.

## Two kinds of activation

| Kind | Meaning | Mechanism |
|---|---|---|
| **Recurring** | "It is now time to execute this capability." | cron |
| **On-demand** | "Somebody has requested this work." | CLI, REST, MCP, and future transports |

Deferred on-demand work is persisted in the **queue** — which is infrastructure, not a source
— until a cron-woken worker claims it.

The domain is transport-independent: adding a transport is an adapter, never a domain change.

## The boundary that defines the product

**Cron activates. TaskControl governs.**

TaskControl does not replace cron and does not require its own always-running scheduler.
Recurring work keeps running when the TaskControl API and web interface are down, because
cron — not TaskControl — wakes it (ADR 0022).

This is the single most important sentence in the product. A capability that would make
recurring work depend on a TaskControl process staying alive is rejected, whatever else it
offers.

## Product pillars

1. **Capability lifecycle management.** Define once; deploy, activate, execute, observe, and
   govern through one consistent lifecycle, whatever activated it.
2. **Recurring activation through managed cron.** Users describe schedules as "every weekday
   at 06:00", or as a validated expression when they prefer. TaskControl renders managed cron
   artefacts, applies them safely, and keeps intended and installed state aligned.
3. **Portable capability packages.** A package placed in an approved directory is discovered,
   validated, and registered — without anyone editing a crontab or changing application code.
4. **Operational knowledge.** Every capability carries purpose, owner, business impact,
   dependencies, runbook, failure procedure, expected duration and frequency, and review
   status. Knowledge is part of the platform, not a feature of it.
5. **On-demand activation through any transport.** CLI, REST, MCP, and future transports are
   adapters over the same application services. Deferred requests are persisted in the queue
   and claimed by cron-woken workers.
6. **Bounded execution services.** Locking, timeout, capture, retries, evidence, and outcome
   classification. Execution answers only "what capability should run"; it owns neither
   scheduling, nor deployment, nor orchestration.

## Product value

Users should be able to answer:

- What work is defined, and why does it exist?
- When is it scheduled, and does the installed schedule match what we intended?
- What is queued, running, complete, or failed right now?
- Did the work achieve its intended outcome, or merely exit zero?
- What was retried, what needs a human, and what changed?
- Who or what initiated each action?

## Design principles

1. **Operational capability is the primary concept.** Activation and execution are separate
   concerns; infrastructure is an adapter, never the centre.
2. **Cron-backed, not cron-replacing.** Recurring activation belongs to a mechanism operators
   already depend on.
3. **Transport-independent.** Adding a transport is an adapter, never a domain change.
4. **Standalone first.** TaskControl delivers value by itself, with no external platform.
5. **General purpose.** The core stays independent of any specific business domain.
6. **Availability over centralisation.** Deployed recurring work survives control-plane
   downtime.
7. **No cron literacy required.** Ordinary authoring never demands cron syntax.
8. **Observable by default.** State, logs, history, and audit evidence are first-class.
9. **Explicit operational truth.** Skip, block, failure, timeout, cancellation, and unproven
   state stay distinct — a zero exit code is not proof of success.
10. **Stable contracts.** Clients integrate through documented interfaces, never internals.
11. **Human control.** Consequential actions can be reviewed, approved, paused, cancelled,
   and audited.
12. **Extensible without capture.** Plugins and adapters extend the product without
    redefining it.

## Explicit non-goals

TaskControl is not:

- a cron replacement, or a permanently running custom scheduler;
- a generic DAG engine competing with Airflow, Temporal, Prefect, or LangGraph;
- a message broker competing with Kafka, RabbitMQ, or Celery;
- a container orchestrator, a CI/CD platform, or an AI-agent framework.

Those systems may integrate with TaskControl or inspire adapters. They do not define its
identity, and a capability that merely makes TaskControl resemble one of them is rejected.

## Responsibility boundary

| Owner | Responsibilities |
|---|---|
| **Cron** | Durable time-based activation; invoking the installed command; continuing to wake jobs when TaskControl's API and UI are unavailable |
| **TaskControl** | Capability definitions and revisions; human-friendly schedule authoring; cron artefact generation and lifecycle; package discovery; inventory and operational knowledge; transport adapters and application services; durable queued request state; execution services; drift, audit, and governance |
| **The runnable** | The domain work itself; its side effects; its own idempotency where repeat execution is possible; domain validation not delegated to TaskControl |

## Product test

A capability belongs in the core when it materially improves at least one of:

1. ordinary users expressing operational intent without understanding cron, queues, or
   runtimes;
2. operators gaining reliable knowledge and control over operational tasks;
3. applications, AI systems, and people safely submitting and inspecting work through any
   transport;
4. cron-backed work staying dependable without a persistent TaskControl scheduler;
5. task state, ownership, changes, and outcomes becoming auditable.

A capability that fails all five is rejected, deferred, or isolated behind an adapter — even
when it is interesting.

## Success criteria for the first release

A user can install TaskControl, define a recurring task without writing a cron expression,
preview and apply the managed cron change, let cron activate it, and inspect the recorded
outcome and history — with the TaskControl web process stopped for the activation itself.

Success does not require KAE, distributed agents, enterprise clustering, or autonomous AI
behaviour.
