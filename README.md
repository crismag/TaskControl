# TaskControl

TaskControl is a **cron-backed operational task management and asynchronous orchestration platform**. It lets people and remote systems define, submit, govern, observe, and maintain operational work without needing to understand cron or run a replacement scheduler.

**Cron activates. TaskControl governs.** TaskControl does not replace cron and does not require an always-running scheduler of its own — your recurring jobs keep running even when the TaskControl API and web interface are down.

It is a general-purpose utility for individuals, teams, services, scripts, CI/CD systems, business applications, and engineering workflows. TaskControl does not depend on KAE or any specific application domain; KAE is one possible external consumer through the same public interfaces available to every other integration.

## The problem

Cron does its job well. What gets lost is everything around it — why a task exists, who owns it, where its runnable lives, whether the installed schedule still matches what anyone intended, what was retried, and what needs a human. TaskControl supplies that missing layer without taking cron's job away.

## Core capabilities

- Define reusable, versioned tasks with schedules expressed as "every weekday at 06:00" — no cron syntax required.
- Generate, plan, apply, and verify **managed cron artefacts**, preserving unmanaged entries.
- Import and adopt an existing cron estate without rewriting it.
- Register drop-in runnable packages from approved directories.
- Track ownership, purpose, runbooks, criticality, and review status.
- Record attempts, outcomes, logs, history, and audit evidence — distinguishing success from a skip, a block, a timeout, and an unproven result.
- Accept durable asynchronous work from remote systems, processed by cron-woken workers.
- Operate through a CLI, REST API, and web application.
- Extend through plugins, adapters, events, and webhooks.

## Example uses

TaskControl can support:

- system administration and maintenance jobs;
- report generation and data-processing pipelines;
- CI/CD and release operations;
- engineering and semiconductor automation flows;
- adopting and documenting an existing cron estate;
- scheduled business processes;
- application-to-application orchestration;
- media, rendering, and batch-processing jobs;
- AI agent and KAE workflows as optional integrations.

## Architectural boundary

```text
        Users, administrators, and remote applications
                            |
              Web UI  /  CLI  /  REST API
                            |
                 TaskControl control plane
                            |
        +-------------------+--------------------+
        |                                        |
 Scheduled task management              Async work submission
        |                                        |
 Cron artefact plan/apply                 Durable work queue
        |                                        |
        v                                        v
      cron  ------------ wakes ------->  short-lived worker
        |                                        |
        +-------------------+--------------------+
                            v
                  Durable claim / lease
                            v
                    Execution services
                            v
              Outcomes, attempts, logs, audit
```

The control plane is optional at activation time. Cron wakes the work; TaskControl records and governs it.

TaskControl Core must remain independent of any specific business domain, AI framework, or external product. Integrations such as KAE, GitHub, CI/CD platforms, notification services, and infrastructure tools connect through stable public contracts.

## Current project stage

**Early implementation.** Waves 0–3 delivered the foundation, domain model, persistence, and execution services under a previous internal-scheduler direction. That direction has been superseded: cron now owns recurring activation ([ADR 0022](development/decisions/0022_CRON_BACKED_ACTIVATION.md)). The completed work is retained and repositioned as supporting execution services.

Cron artefact management, durable claims, and remote submission are the next work.

```bash
make install && make check
.venv/bin/taskctl health
```

See [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) to get set up, and the [implementation blueprint](development/10_IMPLEMENTATION_BLUEPRINT.md) for what is being built next.

### What the first release will and will not do

TaskControl schedules and runs your work itself, through its own scheduler and runtime, observed through its own API, CLI, and web interface. It runs as a persistent local process.

It does **not** yet generate crontab entries or systemd units, deploy to remote hosts, or manage a multi-host estate. Those are Phase 2 and Phase 3 capabilities, deliberately sequenced after execution semantics are proven — see [ADR 0018](development/decisions/0018_INTERNAL_SCHEDULER_BEFORE_ARTEFACT_DEPLOYMENT.md) and the [deferred-capabilities register](development/future/DEFERRED_CAPABILITIES.md).

## Development documentation

Start with [`development/00_CONTEXT_INDEX.md`](development/00_CONTEXT_INDEX.md). It is the only entry point: it carries the file map, the documentation levels, the precedence ladder, and the current status.

- What we build next: [`development/10_IMPLEMENTATION_BLUEPRINT.md`](development/10_IMPLEMENTATION_BLUEPRINT.md)
- Product identity and boundaries: [`development/product/`](development/product/)
- Why every file exists: [`development/DOCUMENTATION_AUDIT.md`](development/DOCUMENTATION_AUDIT.md)

## Product direction

TaskControl is developed first as a useful standalone, cron-backed application. Distributed, enterprise, and ecosystem capability is added incrementally, and never at the cost of the guarantee that already-deployed recurring work keeps running without TaskControl.

## Licence

Not yet chosen — see [`OPEN_QUESTIONS.md`](development/OPEN_QUESTIONS.md) Q1. Until it is, all rights are reserved and the repository is not open for external contribution.
