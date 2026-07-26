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

The repository currently contains the product, domain, architecture, engineering-governance, architecture-decision, and AI-development-operation context required to begin implementation. The next major milestone is the implementation blueprint followed by the first functional application release.

## Development documentation

Start with [`development/README.md`](development/README.md). Product identity and boundaries are defined under [`development/product/`](development/product/).

## Product direction

TaskControl will be developed first as a useful standalone application. Advanced distributed, enterprise, and ecosystem integrations will be added incrementally without weakening the usability of the base product.