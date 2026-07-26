# Product Scope

## Core responsibility

TaskControl owns the lifecycle of automated work from definition through scheduling, execution, observation, and operational governance.

## In scope for the base product

- task definitions and immutable revisions;
- manual, scheduled, delayed, and externally triggered execution;
- dependencies, eligibility rules, retries, timeouts, and cancellation;
- local execution and stable worker abstractions;
- attempt records, outcome evaluation, logs, history, and audit trails;
- approvals and controlled operational actions;
- configuration, secrets references, notifications, and runtime policies;
- web application, REST API, and CLI access;
- plugin, adapter, event, and webhook extension points;
- import, export, backup, recovery, and migration support appropriate to each release.

## Explicit non-goals

TaskControl does not own:

- requirements discovery or product interviewing;
- software architecture generation;
- prompt engineering or model training;
- semantic or long-term AI memory;
- autonomous research and knowledge acquisition;
- source-code generation as a core responsibility;
- business-domain-specific logic;
- KAE internals or lifecycle management.

These systems may submit, control, and observe tasks through public interfaces.

## First functional release boundary

The first product release should provide:

1. installation and local startup;
2. task creation and revision management;
3. manual execution;
4. basic scheduling;
5. execution state, logs, history, cancellation, and retry;
6. persistence and restart recovery;
7. a practical CLI and web interface;
8. documented public API foundations;
9. tests, migrations, configuration, and operational documentation.

## Deferred capabilities

The following remain future phases unless required by evidence:

- distributed worker fleets;
- high availability and clustering;
- complex tenancy and enterprise federation;
- marketplace-style plugins;
- advanced policy engines;
- large-scale event streaming;
- deep KAE-specific adapters.

Deferral must not prevent clean extension points, but it must prevent premature implementation complexity.