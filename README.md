# TaskControl

TaskControl is a standalone application for defining, scheduling, executing, monitoring, and governing automated work.

It is designed as a general-purpose task orchestration utility that can be used by individuals, teams, services, scripts, CI/CD systems, business applications, engineering workflows, and AI-enabled platforms. TaskControl does not depend on KAE or any specific application domain. KAE is one possible external consumer of TaskControl through the same public interfaces available to every other integration.

## Product purpose

TaskControl turns task definitions into reliable, observable, and auditable operations. It brings scheduling, execution control, dependencies, retries, approvals, deployment, monitoring, history, and runtime policies into one extensible application.

## Core capabilities

- Define reusable and versioned tasks.
- Schedule recurring, delayed, and event-driven work.
- Execute commands, scripts, services, and adapter-backed operations.
- Model dependencies, eligibility, retries, timeouts, and approvals.
- Track attempts, outcomes, logs, history, and audit evidence.
- Operate through a web application, REST API, CLI, and future SDKs.
- Extend the platform through plugins, adapters, workers, events, and webhooks.

## Example uses

TaskControl can support:

- system administration and maintenance jobs;
- report generation and data-processing pipelines;
- CI/CD and release operations;
- engineering and semiconductor automation flows;
- scheduled business processes;
- application-to-application orchestration;
- media, rendering, and batch-processing jobs;
- AI agent and KAE workflows as optional integrations.

## Architectural boundary

```text
External clients and applications
        |
REST API / CLI / Web UI / SDK / Webhooks
        |
TaskControl application services and domain core
        |
Scheduler / execution engine / persistence / audit / plugins
        |
Local runners and future remote workers
```

TaskControl Core must remain independent of any specific business domain, AI framework, or external product. Integrations such as KAE, GitHub, CI/CD platforms, notification services, and infrastructure tools connect through stable public contracts.

## Current project stage

**Early implementation — Wave 0 complete.** The project installs, passes lint, strict type checking, and its test suite, and exposes version and health through both the CLI and the API. There is no task, scheduling, or execution behaviour yet; that begins with Wave 1.

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

TaskControl will be developed first as a useful standalone application. Advanced distributed, enterprise, and ecosystem integrations will be added incrementally without weakening the usability of the base product.

## Licence

Not yet chosen — see [`OPEN_QUESTIONS.md`](development/OPEN_QUESTIONS.md) Q1. Until it is, all rights are reserved and the repository is not open for external contribution.
