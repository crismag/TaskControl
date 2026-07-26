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

- Run recurring scripts with logs and failure history.
- Replace fragile unmanaged cron entries.
- Start, pause, retry, or cancel long-running jobs.

### Engineering workflows

- Run simulations, verification flows, builds, packaging, and release preparation.
- Coordinate dependent commands and inspect every attempt.
- Gate consequential steps behind approvals.

### Business and ministry operations

- Generate scheduled reports.
- Process recurring records and notifications.
- Track completion and exceptions for operational routines.

### Application orchestration

- Allow another application to create or trigger work through the REST API.
- Receive completion events through webhooks.
- Keep execution logic outside the calling application.

### AI-enabled workflows

- Execute tools or agent-produced task plans.
- Apply timeouts, retries, permissions, approvals, and audit controls to AI-triggered work.
- Return structured results without making AI concepts part of the core domain.

## Product usability standard

The base application must remain understandable to a user who has no knowledge of KAE, AI agents, distributed systems, or enterprise workflow products.
