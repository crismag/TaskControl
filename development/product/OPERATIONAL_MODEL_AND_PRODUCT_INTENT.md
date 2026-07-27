# Operational Model and Product Intent

- Document level: **0 — Identity**
- Lifecycle state: Canonical
- Status: Intentionally historical and conceptual
- Related: `PRODUCT_VISION.md`, `PRODUCT_SCOPE.md`, ADR 0022

## Purpose

This document explains the real operational model that inspired TaskControl.

It is intentionally historical and conceptual.

Implementation decisions must preserve this model even when the internal implementation
evolves.

---

## This is NOT a new computing concept

TaskControl is **not** attempting to invent:

- another scheduler
- another message broker
- another workflow engine
- another application server

Instead, it productises operational practices that production engineers and system
administrators have manually implemented for decades.

Many large organisations already operate in a similar manner using shell scripts, cron,
deployment systems, monitoring, wrappers, logging, and operational runbooks.

TaskControl simply provides a reusable implementation.

---

## Historical background

The product originates from production engineering experience.

Example responsibilities included:

- editing cron definitions
- deploying scheduled work
- market-open preparation
- market-close processing
- health checks
- sanity checks
- monitoring hundreds of servers
- data movement between systems
- scheduled reporting
- scheduled notifications
- operational alerting

Cron was only one small piece of this ecosystem.

The real job was operating production systems safely.

---

## The traditional operational model

A production engineer writes or updates a task.

Example:

```text
backup_database.sh
```

or

```text
market_close_processing.sh
```

The engineer specifies when it should execute.

Eventually the system deploys the schedule.

cron performs activation.

The script executes.

Logs are produced.

Alerts may be generated.

Reports are updated.

The engineer is informed if intervention is required.

Nothing about this workflow requires a permanently running scheduler.

Cron is simply the operating system's activation mechanism.

---

## Existing deployment systems

Large organisations have historically used deployment systems that distribute cron changes
to many servers.

The operational flow is approximately:

```text
Engineer
   |
Modify operational definition
   |
Deployment system
   |
Relevant servers
   |
cron
   |
Wrapper / Script
   |
Operational work
   |
Logs / Alerts / Reports
```

TaskControl is inspired by this model.

The objective is to make this operational capability reusable.

---

## Why TaskControl generates cron entries

The product intentionally owns cron deployment.

Users should not manually edit crontab.

Instead they define operational work.

TaskControl determines:

- schedule
- validation
- installation
- updates
- rollback
- verification
- enable / disable
- adoption of existing cron entries

Cron remains the operating system scheduler.

TaskControl manages the lifecycle around it.

---

## Operational work

The primary concept is operational work.

Examples:

- backup
- cleanup
- report generation
- deployment
- notification
- monitoring
- reconciliation
- health checks

Operational work may be activated through multiple mechanisms.

| Activation | Mechanism |
|---|---|
| Recurring activation | cron |
| One-time activation | queue |
| Immediate activation | CLI |
| Remote activation | REST API |
| AI activation | MCP |

The activation mechanism does not change the operational work itself.

> **Refined later.** These five were subsequently reduced to **two kinds of activation** —
> recurring (cron) and on-demand (CLI, REST, MCP), with the queue as the persistence
> mechanism for deferred on-demand requests. See `PRODUCT_DESIGN_VISION.md` and ADR 0025.

---

## Why small executable tasks

Operational systems naturally evolve into many small executable units.

Instead of one monolithic automation application:

```text
deploy_everything.py
```

TaskControl encourages:

```text
backup/
cleanup/
report/
notify/
sync/
```

Each package performs one operational capability.

Advantages:

- independently testable
- independently deployable
- reusable
- portable
- version controlled
- understandable

TaskControl orchestrates them.

---

## Queue philosophy

The queue is NOT a separate product.

It exists because production systems frequently require deferred work.

Historically this was often implemented as:

```text
Application
   |
Database
   |
cron wakes
   |
claim work
   |
execute
   |
record outcome
```

TaskControl standardises this proven pattern.

The queue is therefore another activation source for operational work.

> **Refined later.** The stable model treats the queue as **infrastructure**, not an
> activation source: it persists deferred on-demand requests until a cron-woken worker claims
> them, and the activation source is the *request* that created them. See
> `PRODUCT_DESIGN_VISION.md` and ADR 0025. The pattern described above is unchanged; only its
> naming is.

---

## MCP

MCP is another activation mechanism.

AI agents may submit operational work through MCP.

The work still follows the same lifecycle:

```text
submit
   |
persist
   |
activate
   |
execute
   |
observe
   |
audit
```

Nothing about AI changes the execution model.

---

## What TaskControl is

TaskControl is an operational automation platform.

It captures decades of proven production engineering practices and makes them reusable.

It manages operational work throughout its lifecycle:

```text
definition
deployment
activation
execution
observation
governance
history
audit
```

Cron is deliberately used because it is mature, reliable, operating-system native, and
independent of TaskControl's runtime.

TaskControl does not replace cron.

It automates everything that experienced production engineers traditionally built around
cron.
