# Product Design Vision

- Document level: **0 — Identity**
- Lifecycle state: Canonical
- Status: Conceptual design vision, written from the operations-engineer perspective
- Related: `OPERATIONAL_MODEL_AND_PRODUCT_INTENT.md`, `PRODUCT_VISION.md`, ADR 0022

## Purpose

This document explains the conceptual design vision behind TaskControl.

It intentionally describes the product from the perspective of an operations engineer rather
than from the perspective of software implementation.

It exists to help future contributors understand why architectural decisions are made.

---

## The problem

Today's operational automation is fragmented.

Recurring work is managed by cron.

One-time work is often implemented by custom database queues.

Monitoring is implemented separately.

Documentation is stored elsewhere.

Runbooks are separate documents.

Ownership is tribal knowledge.

Every organisation builds a different solution.

TaskControl attempts to unify these proven operational patterns into a single operational
platform.

---

## Core Philosophy

TaskControl is not centred around scheduling.

TaskControl is centred around **operational work**.

Scheduling is only one way operational work becomes active.

Queue submission is another.

REST requests are another.

AI systems are another.

Manual execution is another.

The work itself remains identical.

---

## Operational Work Lifecycle

Every operational capability follows the same lifecycle.

```text
Design
  ↓
Register
  ↓
Validate
  ↓
Deploy
  ↓
Activate
  ↓
Execute
  ↓
Observe
  ↓
Record
  ↓
Improve
```

Different activation mechanisms should not require different execution implementations.

---

## Operational Capability

TaskControl encourages automation to be written as small operational capabilities.

Examples:

```text
backup/
cleanup/
market_close/
send_report/
health_check/
sync_exchange/
reconcile/
```

Each capability should be:

- independently executable
- independently testable
- independently deployable
- independently observable
- independently documented

TaskControl manages the lifecycle around these capabilities.

---

## Activation Sources

Operational capabilities may become active through several mechanisms.

| Activation | Mechanism |
|---|---|
| Recurring | `cron` |
| One-time | `Queue` |
| Immediate | `CLI` |
| External application | `REST API` |
| AI | `MCP` |

Future activation sources should not require redesign of the execution model.

---

## Task Packages

Operational capabilities should be portable.

Example:

```text
backup/
    task.yaml
    run.sh
    README.md
    config/
    tests/
```

The package should contain everything required to understand and execute the capability.

TaskControl discovers packages instead of requiring application code changes.

---

## Cron Management

TaskControl intentionally manages cron.

Users should not manually edit crontab files.

Instead they define desired operational behaviour.

TaskControl becomes responsible for:

- validation
- rendering
- deployment
- updates
- verification
- rollback
- enable / disable
- adoption
- drift detection

Cron remains the operating system scheduler.

TaskControl manages its lifecycle.

---

## Queue Processing

The queue is another activation mechanism.

Applications submit operational work.

TaskControl stores durable work.

Cron activates queue workers.

Workers claim eligible work.

Operational capabilities execute.

Results are recorded.

The queue therefore shares the same execution model as scheduled work.

---

## Execution

Execution should remain intentionally simple.

The execution layer should only answer:

> "What operational capability should be executed?"

Execution should not own scheduling.

Execution should not own deployment.

Execution should not own orchestration.

Execution consumes work.

---

## Operational Knowledge

Every operational capability should describe itself.

Examples:

- Purpose
- Owner
- Business impact
- Dependencies
- Runbook
- Failure procedure
- Documentation
- Expected duration
- Expected frequency
- Related systems

TaskControl should preserve operational knowledge alongside execution.

---

## Platform Architecture

The conceptual architecture is:

```text
                 Operational Work
                        │
      ┌─────────────────┼──────────────────┐
      │                 │                  │
   Scheduled        On-demand             AI
      │                 │                  │
    cron             Queue/API           MCP
      └─────────────────┼──────────────────┘
                        │
                Execution Engine
                        │
                Operational State
                        │
          History • Audit • Metrics • Logs
```

Activation should never redefine execution.

---

## Design Principles

1. Operational work is the primary domain concept.
2. Activation and execution are separate concerns.
3. Cron remains the operating system scheduler.
4. TaskControl manages operational lifecycle.
5. Small executable capabilities are preferred over monolithic automation.
6. Every operational capability should be portable.
7. Every execution should be observable.
8. Operational knowledge is part of the platform.
9. Future activation mechanisms should reuse the same execution model.
10. The platform should simplify operational engineering rather than expose implementation
    complexity.

---

## Long-Term Vision

TaskControl should become the platform where operational work is defined once and activated
through any supported mechanism.

The product should eventually support:

- recurring operational automation
- asynchronous operational work
- AI-driven operational execution
- distributed execution
- reusable operational capability libraries
- operational governance
- operational knowledge management

without changing the fundamental lifecycle of operational work.

The goal is not to replace proven operating system capabilities.

The goal is to provide the operational control plane that experienced production engineers
have historically built manually around those capabilities.
