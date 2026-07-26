> **STATUS: SUPERSEDED** — replaced by `development/product/PRODUCT_VISION.md` and `development/product/PRODUCT_PHILOSOPHY.md`.
>
> Retained for historical reasoning. **Do not use for new implementation.**
>
> Superseded: 2026-07-26. Reason: Cron-centric product framing replaced by the standalone general-purpose positioning of PR #7. Differentiators and the cron-transformation thesis survive in `development/future/DEFERRED_CAPABILITIES.md` (Phase 2 generation) and ADR 0018.

---

# Product Vision

## Product statement

TaskControl transforms task definitions into reliable, observable, and production-ready scheduled operations by unifying scheduling, runtime controls, execution, deployment, monitoring expectations, and governance.

## Tagline

**Define once. Deploy anywhere. Operate with confidence.**

## Problem

Scheduled automation is commonly scattered across user crontabs, shell scripts, environment profiles, run-parts directories, service accounts, host-specific conventions, monitoring checks, and undocumented operational knowledge. Small installations are difficult to understand; large estates become fragile, duplicated, hard to audit, and risky to change.

Enterprise workload schedulers address parts of this problem but can be expensive, infrastructure-heavy, proprietary, and disconnected from the scripts and configuration practices used by Linux and engineering teams. Lightweight cron tools usually edit schedules but do not model the complete operational lifecycle.

## Product transformation

TaskControl turns:

- commands and scripts into managed tasks;
- cron expressions into understandable schedules;
- shell profiles into reusable, layered environment profiles;
- holiday checks and application switches into explicit run conditions;
- host-specific deployments into inventory-based deployment instances;
- exit codes into classified execution outcomes;
- informal expectations into monitoring contracts;
- manually edited artefacts into reproducible generated packages;
- isolated cron estates into centrally understandable operations.

## Primary product principles

1. **Definition before generation** — declarative task definitions are authoritative.
2. **Local reliability before central dependence** — deployed tasks should continue operating when the control plane is temporarily unavailable.
3. **Progressive scale** — the same conceptual model supports personal, team, fleet, enterprise, and federated use.
4. **Adapter-based portability** — cron is the first scheduler adapter, not the domain model.
5. **Observable decisions** — success, failure, skip, block, timeout, cancellation, and suppression are distinct outcomes.
6. **Operational context is first-class** — calendars, profiles, switches, identities, expected outputs, and monitoring belong to the task lifecycle.
7. **Safe generation** — generated scripts and scheduler artefacts are deterministic, reviewable, versionable, and testable.
8. **Open integration** — Bash, Python, Tcl, executables, HTTP, SQL, cron, systemd, Kubernetes, Windows, Nagios, and future systems integrate through explicit adapters.

## Initial target users

- Individual Linux users managing personal automation.
- Developers and support engineers managing application jobs.
- DevOps and platform teams managing multi-user and multi-host task estates.
- Engineering organisations using Bash, Python, Tcl, EDA tools, and shared compute environments.
- Operations organisations managing business calendars, runtime switches, monitoring, and controlled deployments.

## Product boundaries

TaskControl is initially a scheduled-task operations platform, not a full replacement for Airflow, Control-M, Nagios, Kubernetes, or a general-purpose CI/CD system. It should integrate with those categories where useful while delivering a coherent experience around scheduled operational tasks.

The first release should not attempt global active-active federation, advanced workflow DAG scheduling, proprietary enterprise integrations, or a compiled agent. These remain planned extension areas.

## Initial differentiators

- Task generation with production-grade logging, locking, retry, timeout, environment, and notification patterns.
- Explicit separation of trigger and run conditions.
- Reusable business calendars and runtime switches without editing cron entries.
- Local-first execution with central management as an optional scale-up path.
- One task model spanning cron, systemd, and later platform adapters.
- Monitoring expectations that describe what should happen, not merely whether a process exited zero.
- Strong support for existing Bash, Python, and Tcl estates.
