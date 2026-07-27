# TaskControl Product Philosophy

- Document level: **0 — Identity**
- Governed by: `PRODUCT_VISION.md`, `PRODUCT_SCOPE.md`
- Related: ADR 0016 (outcomes), ADR 0022 (cron owns activation)

## Purpose

TaskControl exists to turn operational intent into reliable, observable, governable automated work.

The product must not be designed as a graphical editor for cron syntax. Cron is the
dependable substrate underneath, not the interface on top: a user should never need to write
a cron expression for ordinary authoring, and should never be prevented from reading or
overriding the artefact TaskControl generates. The user should describe what must happen, when it should happen, where it should run, under what conditions it is allowed to run, and what outcome proves success. TaskControl is responsible for turning that intent into execution and operational control.

> **TaskControl automates the work of production engineers, not just the execution of scripts.**

This is the primary product rule. Every feature, API, screen, schema, adapter, and workflow should be evaluated against it.

Production engineers do not think in queues, schedulers, and runtimes. They think:

- "Run this tomorrow after market close."
- "Roll this out to the production fleet."
- "Tell me if anything fails."
- "Generate the daily report."
- "Retry the failed reconciliation."

TaskControl should let them express those operational intentions and handle the mechanics underneath. A feature that makes the mechanics more visible rather than less is usually the wrong feature.

Restated for implementation: *the user defines intent; TaskControl resolves it into safe, observable execution.*

## Small, portable capabilities

Operational systems evolve into many small executable units, not one monolithic automation application. TaskControl encourages that and manages the lifecycle around it.

A capability package should carry everything needed to understand and execute it:

```text
backup/
    task.yaml
    run.sh
    README.md
    config/
    tests/
```

Each capability should be independently executable, testable, deployable, observable, and documented. TaskControl **discovers** packages rather than requiring application code changes — which is why drop-in discovery is a design position, not a convenience feature.

## How intent becomes activation

TaskControl renders a task's schedule into a **managed artefact for an external scheduler**, and that scheduler activates the work. Cron is the first and primary target (ADR 0022); systemd timers and platform schedulers follow as further adapters.

TaskControl does not activate recurring work itself. It never runs a timer, a polling loop, or an always-on scheduler process. A generated artefact invokes a short-lived TaskControl wrapper, which applies the execution services — locking, timeout, capture, classification — and exits.

Run-now exists for administration and validation. It is not the scheduled-job workflow.

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
| --- | --- |
| Schedule | cron, systemd timer, Kubernetes CronJob, Windows task |
| Run condition | Python evaluator, shell guard, remote policy decision |
| Runtime profile | environment file, secret reference, container environment |
| Deployment target | local host, SSH host, agent, cluster, region |
| Expected outcome | file check, API check, freshness check, row-count check |
| Monitoring | internal history, Nagios, Prometheus, webhook, email |

The domain model must remain independent from any one scheduler or operating system.

## Progressive disclosure

The simplest useful experience should be possible without understanding enterprise architecture.

A personal user should be able to create a task, select a schedule, test it, install the
managed cron entry, and view execution history — without opening a crontab. The same task may later gain reusable profiles, calendars, run conditions, multiple targets, approvals, monitoring expectations, enterprise ownership, and delegated administration.

Complexity should appear only when the user's operating context requires it.

## Explicit operational states

TaskControl must distinguish states that traditional cron environments blur together. A skip is not a failure. A zero exit code is not necessarily operational success. A guard that prevented a start is not the same as a policy that declined to run.

These distinctions must survive into the domain model, API, UI, logs, metrics, and notifications. **The normative vocabulary is defined once, in ADR 0016.** This document does not restate it.

## Generated artefacts are inspectable

Managed cron artefacts, resolved configuration snapshots, validation output, and execution
records are all covered by this rule.

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

## Where this document does not decide

Product philosophy sets the standard a feature must meet. It does not decide delivery order, scope boundaries, or vocabulary. Those belong to `PRODUCT_ROADMAP.md`, `PRODUCT_SCOPE.md`, and the ADRs respectively.
