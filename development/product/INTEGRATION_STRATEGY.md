# Integration Strategy

- Document level: **0 — Identity**
- Lifecycle state: Canonical

## Goal

Allow external systems to use and extend TaskControl without depending on private implementation details.

## The governing rule

> **The domain model SHALL remain transport-independent. MCP, REST, CLI, and future
> transports are adapters over the same application services** (ADR 0025).

Every transport calls the same application service to submit an execution request. The
domain neither knows nor cares which one called; the mechanism is recorded as provenance on
the request, never consulted as a branch.

If adding a transport would require a domain change, the domain is wrong.

## Supported integration surfaces

- REST API for task, execution, scheduling, history, and administration operations.
- Asynchronous work-item submission returning durable acceptance rather than waiting for
  execution.
- CLI for people, scripts, CI/CD, and local automation.
- Webhooks and events for external reactions to lifecycle changes.
- Plugins and adapters for execution backends, schedulers, notifications, secrets, and infrastructure.
- MCP, so AI systems submit operational work through the same lifecycle as any other caller.
  Nothing about AI changes the execution model.
- Future SDKs, gRPC, or GraphQL surfaces, generated or maintained against the same
  application services.
- Import and export formats for portable task definitions and operational data where appropriate.

## Contract rules

1. Integrations use versioned public contracts.
2. Domain concepts remain general and implementation-neutral.
3. Internal database tables and private modules are not integration APIs.
4. Authentication and authorisation apply consistently to human and machine clients.
5. Idempotency, retries, timeouts, correlation identifiers, and error semantics are explicit.
6. Integration-specific metadata is namespaced and cannot redefine core behaviour.
7. Breaking changes require migration guidance and an appropriate compatibility policy.
8. Remote callers submit **registered task types and work items**, never arbitrary shell
   commands. A submission API that accepts an arbitrary command is a remote-execution
   service, which is not what this product is.
9. Submission is asynchronous and durable by default. A caller receives an identifier and an
   accepted status; cron later wakes a bounded worker to process the item.

## Integration categories

### Transports

Web UI, CLI, REST, MCP, scripts, SDKs, business applications, KAE, and AI agents. All are
adapters over the same application services, and none is privileged.

### Execution adapters

Local processes, containers, remote workers, CI systems, infrastructure tools, and specialised engineering runtimes.

### Trigger adapters

Internal schedules, external webhooks, repository events, message systems, and future event sources.

### Operational adapters

Notifications, observability, secrets, identity, storage, audit export, and backup systems.

## KAE integration

KAE must integrate as a normal external client or adapter. Any KAE-specific translation belongs in a separate integration package or repository boundary. The TaskControl public API must remain complete and coherent without that integration.

## Acceptance test for new integrations

A proposed integration is correctly designed when TaskControl can remove it without changing core domain semantics and the integration can be replaced by another implementation using the same port or public contract.
