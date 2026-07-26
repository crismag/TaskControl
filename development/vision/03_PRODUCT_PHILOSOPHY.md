# TaskControl Product Philosophy

## Purpose

TaskControl exists to turn operational intent into reliable, observable, deployable scheduled operations.

The product must not be designed as a graphical editor for cron syntax. Cron is only one possible target. The user should describe what must happen, when it should happen, where it should run, under what conditions it is allowed to run, and what outcome proves success. TaskControl is responsible for transforming that intent into implementation artefacts and operational controls.

> The user defines intent. TaskControl generates implementation.

This sentence is the primary product rule. Every feature, API, screen, schema, adapter, and workflow should be evaluated against it.

## What users should think about

Users should think in operational concepts:

- Run the settlement reconciliation every weekday at 06:00.
- Do not run when the London market calendar is closed.
- Use the production reconciliation profile.
- Run as the `settlement` service account on the accounting host group.
- Retry twice for transient failures.
- Fail if the expected report is not produced within 20 minutes.
- Notify the operations team when the result is late or failed.

Users should not need to begin with implementation details such as crontab line formatting, systemd unit syntax, Kubernetes manifests, Windows Task Scheduler XML, shell profile sourcing, lock-file conventions, or monitoring plug-in arguments.

Advanced users may inspect, override, or extend generated artefacts, but implementation syntax must not be the product's primary mental model.

## Intent before mechanism

TaskControl should expose stable domain concepts and hide replaceable mechanisms.

| User intent | Possible generated mechanisms |
|---|---|
| Schedule | cron, systemd timer, Kubernetes CronJob, Windows task |
| Run condition | Python evaluator, shell guard, remote policy decision |
| Runtime profile | environment file, secret reference, container environment |
| Deployment target | local host, SSH host, agent, cluster, region |
| Expected outcome | file check, API check, freshness check, row-count check |
| Monitoring | internal history, Nagios, Prometheus, webhook, email |

The domain model must remain independent from any one scheduler or operating system.

## Progressive disclosure

The simplest useful experience should be possible without understanding enterprise architecture.

A personal user should be able to create a task, select a schedule, test it locally, install it, and view execution history. The same task may later gain reusable profiles, calendars, run conditions, multiple targets, approvals, monitoring expectations, enterprise ownership, and delegated administration.

Complexity should appear only when the user's operating context requires it.

## Explicit operational states

TaskControl must distinguish states that traditional cron environments frequently blur together.

A triggered task may become:

- permitted and started;
- skipped because a calendar is closed;
- skipped because a feature switch is disabled;
- blocked because a dependency is unhealthy;
- rejected because configuration is invalid;
- failed before the command starts;
- started and completed successfully;
- started and completed with a process failure;
- completed at process level but failed an expected-outcome check;
- timed out;
- cancelled;
- lost because an executor became unavailable.

A skip is not a failure. A zero process exit code is not necessarily operational success. The platform must preserve these distinctions in the domain model, API, UI, logs, metrics, and notifications.

## Generated artefacts are inspectable

Generated content should be deterministic where practical, versioned, diffable, validated before deployment, attributable to a task revision, reproducible from stored intent, and safe to preview without applying changes.

The user must be able to answer:

- What will be installed?
- Where will it be installed?
- What changed?
- Which task revision produced it?
- Which profile and policies were resolved?
- Who approved or deployed it?
- Can it be rolled back?

## Local-first, enterprise-capable

The first implementation should work well for one user on one machine. It must not require a distributed control plane to deliver value.

However, the conceptual model must remain valid when expanded to many users, many service accounts, many hosts, mixed operating systems, several scheduler technologies, multiple environments and regions, separate business units or tenants, disconnected sites, and delegated administration.

Do not create a separate conceptual product for enterprise operation. Extend the same task, target, profile, deployment, execution, and expectation concepts.

## Reliability is a feature

TaskControl is an operations product. Reliability requirements belong in the product design.

The system should favour idempotent deployment, explicit locking and concurrency policies, durable execution records, recoverable worker behaviour, clear timeouts, controlled retries, immutable audit events, safe defaults, dry-run and preview modes, validation before side effects, and explainable decisions.

A polished interface cannot compensate for ambiguous operational behaviour.

## Safe extension rather than premature generalisation

TaskControl should use extension points where multiple implementations are expected, including scheduler adapters, execution adapters, deployment adapters, run-condition providers, calendar providers, secret providers, expectation evaluators, notification providers, and monitoring exporters.

Do not convert every internal class into a plug-in. Introduce interfaces at genuine volatility boundaries, not as ceremony.

## Product language

Prefer product terms such as Task, Schedule, Target, Runtime Profile, Run Condition, Calendar, Deployment Plan, Execution, Expected Outcome, Notification Rule, and Scheduler Adapter.

A crontab entry, systemd timer, or Kubernetes CronJob is a generated or managed scheduler artefact, not the task itself.

## Human and AI maintainability

The repository will be developed with substantial AI assistance. Architecture and code must therefore be explicit enough for both humans and coding agents to follow.

Important rules should be represented through module boundaries, tests, schemas, type hints, architecture decision records, development documentation, validation rules, and clear naming.

## Product test

Before accepting a major feature, ask:

1. Does it help users express operational intent?
2. Does it preserve the distinction between definition, deployment, execution, and observation?
3. Can its behaviour be explained before side effects occur?
4. Can it work locally while remaining compatible with future multi-host operation?
5. Does it improve reliability, auditability, or usability?
6. Is the mechanism replaceable without rewriting the domain model?
7. Can generated output be inspected and reproduced?

When the answer is no, reconsider the design.