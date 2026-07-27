# Users and Use Cases

- Document level: **0 — Identity**
- Lifecycle state: Canonical

## Primary users

- Individual developers and administrators running recurring or ad hoc automation.
- Engineering teams managing build, verification, data-processing, and release jobs.
- Operations teams controlling maintenance, reporting, backup, deployment, and recovery work.
- Application teams that need a reusable orchestration service instead of building custom schedulers.
- Small organisations that need an understandable automation utility with history and accountability.

## Secondary users

- Platform and enterprise teams integrating remote workers, policies, identity, and observability.
- External applications invoking TaskControl through APIs, SDKs, webhooks, or plugins.
- AI agents and KAE components that need reliable execution and monitoring infrastructure.

## Representative use cases

### Personal and local automation

- Schedule recurring scripts without writing cron expressions, and keep logs and failure
  history.
- Bring existing unmanaged cron entries under management without rewriting them.
- Pause, resume, retry, or cancel jobs, and see why a run did not happen.

### Engineering workflows

- Run simulations, verification flows, builds, packaging, and release preparation.
- Coordinate dependent commands and inspect every attempt.
- Gate consequential steps behind approvals.

### Business and ministry operations

- Generate scheduled reports.
- Process recurring records and notifications.
- Track completion and exceptions for operational routines.

### Application orchestration

- Allow another application to submit durable asynchronous work through the REST API,
  without SSH, filesystem access, or crontab edits.
- Receive an immediate acceptance and inspect terminal status later.
- Receive completion events through webhooks.
- Keep execution logic outside the calling application.

### AI-enabled workflows

- Execute tools or agent-produced task plans.
- Apply timeouts, retries, permissions, approvals, and audit controls to AI-triggered work.
- Return structured results without making AI concepts part of the core domain.

## Product usability standard

The base application must remain understandable to a user who has no knowledge of KAE, AI
agents, distributed systems, or enterprise workflow products — **and no knowledge of cron
syntax**. Cron is the dependable mechanism underneath; understanding it must never be a
prerequisite for ordinary use.
