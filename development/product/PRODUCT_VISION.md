# Product Vision

- Document level: **0 — Identity**
- Lifecycle state: Canonical
- Governs: everything below Level 0. When another document disagrees with this one, this one is right.
- Related: ADR 0022 (cron owns recurring activation)

## Mission

Make operational work easy to define, dependable to activate, simple to observe, and safe to
govern — without replacing the scheduler an operator already trusts.

## North star

> **TaskControl is a cron-backed operational task management and asynchronous orchestration
> platform. It lets people and remote systems define, submit, govern, observe, and maintain
> operational work without requiring users to understand cron or operate a replacement
> scheduler.**

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

## The boundary that defines the product

**Cron activates. TaskControl governs.**

TaskControl does not replace cron and does not require its own always-running scheduler.
Recurring work keeps running when the TaskControl API and web interface are down, because
cron — not TaskControl — wakes it (ADR 0022).

This is the single most important sentence in the product. A capability that would make
recurring work depend on a TaskControl process staying alive is rejected, whatever else it
offers.

## Product pillars

1. **Cron-backed task management.** Users describe schedules as "every weekday at 06:00", or
   as a validated expression when they prefer. TaskControl renders managed cron artefacts,
   applies them safely, and keeps intended and installed state aligned.
2. **Drop-in runnable management.** A runnable and its metadata placed in an approved
   directory is discovered, validated, and registered — without anyone editing a crontab.
3. **Operational knowledge.** Every task carries purpose, owner, source, schedule, target,
   criticality, runbook, inputs, outputs, dependencies, review status, and evidence.
4. **Remote operations API.** Other systems manage jobs and submit work through
   authenticated contracts rather than SSH, filesystem edits, or crontab manipulation.
5. **Cron-woken asynchronous queue.** Remote callers submit durable work items. Cron
   periodically wakes short-lived workers that claim, process, retry, and record them.
6. **Optional execution services.** TaskControl can wrap execution to add locking, timeout,
   logging, evidence, retries, and outcome classification. These support management and
   observability; they never become the recurring scheduler.

## Product value

Users should be able to answer:

- What work is defined, and why does it exist?
- When is it scheduled, and does the installed schedule match what we intended?
- What is queued, running, complete, or failed right now?
- Did the work achieve its intended outcome, or merely exit zero?
- What was retried, what needs a human, and what changed?
- Who or what initiated each action?

## Design principles

1. **Cron-backed, not cron-replacing.** Activation belongs to a mechanism operators already
   depend on.
2. **Standalone first.** TaskControl delivers value by itself, with no external platform.
3. **General purpose.** The core stays independent of any specific business domain.
4. **Availability over centralisation.** Deployed recurring work survives control-plane
   downtime.
5. **No cron literacy required.** Ordinary authoring never demands cron syntax.
6. **Observable by default.** State, logs, history, and audit evidence are first-class.
7. **Explicit operational truth.** Skip, block, failure, timeout, cancellation, and unproven
   state stay distinct — a zero exit code is not proof of success.
8. **Stable contracts.** Clients integrate through documented interfaces, never internals.
9. **Human control.** Consequential actions can be reviewed, approved, paused, cancelled,
   and audited.
10. **Extensible without capture.** Plugins and adapters extend the product without
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
| **TaskControl** | Task definitions and revisions; human-friendly schedule authoring; cron artefact generation and lifecycle; drop-in discovery; task inventory and operational knowledge; remote API contracts; durable queued work state; execution services; drift, audit, and governance |
| **The runnable** | The domain work itself; its side effects; its own idempotency where repeat execution is possible; domain validation not delegated to TaskControl |

## Product test

A capability belongs in the core when it materially improves at least one of:

1. ordinary users managing scheduled work without understanding cron;
2. operators gaining reliable knowledge and control over operational tasks;
3. remote systems safely submitting and inspecting asynchronous work;
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
