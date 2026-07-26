> **STATUS: SUPERSEDED** — replaced by `development/product/PRODUCT_ROADMAP.md` (phases) and `development/10_IMPLEMENTATION_BLUEPRINT.md` (waves).
>
> Retained for historical reasoning. **Do not use for new implementation.**
>
> Superseded: 2026-07-26. Reason: Waves 0-10 were one of three competing delivery partitions. Wave 4-10 capability content is preserved in `development/future/DEFERRED_CAPABILITIES.md`. Wave ordering superseded by ADR 0018.

---

# Delivery Roadmap

## Wave 0 — Repository foundation

Deliver documentation, Python project configuration, quality tooling, CI, licensing decision, contribution guidance, architecture decision records, and a minimal importable package.

Exit criteria:
- clean install in a virtual environment;
- tests, lint, and type checks pass;
- documented local developer workflow;
- no product behaviour beyond a health/version command.

## Wave 1 — Domain and definition engine

Implement typed task, executor, trigger, runtime-control, profile, condition, deployment, execution, and expectation models.

Deliver:
- YAML/JSON load and dump;
- schema validation;
- semantic validation;
- stable identifiers and versions;
- example task definitions;
- JSON Schema export;
- unit tests for invariants.

## Wave 2 — Local runtime

Implement `taskctl run` with:
- shell command and executable adapters;
- Python and Tcl subprocess adapters;
- stdout/stderr capture;
- structured logs;
- timeout;
- retry and backoff;
- working directory and environment resolution;
- overlap locking;
- explicit outcome classification;
- durable SQLite execution history.

Exit criteria: a local task can be validated, executed, inspected, retried, skipped, and audited.

## Wave 3 — Schedules, calendars, and run conditions

Implement:
- cron parsing and next-run preview;
- timezone handling;
- business calendars;
- holiday include/exclude dates;
- runtime switches;
- reusable condition evaluation;
- reasoned skip records;
- schedule simulation tests around DST and holidays.

## Wave 4 — Cron deployment

Implement:
- managed crontab rendering;
- import and classification of existing cron entries;
- deployment plans and diffs;
- atomic apply and rollback;
- managed blocks rather than destructive replacement;
- ownership and permission checks;
- drift detection for local mode.

## Wave 5 — API and initial web interface

Implement FastAPI endpoints for definitions, validation, execution, schedules, deployments, and history. Add a TypeScript interface for task creation, schedule preview, runtime controls, run conditions, execution history, and deployment review.

## Wave 6 — Profiles, collections, and monitoring contracts

Implement layered profiles, provenance display, task collections, expected outcomes, generic monitoring contracts, and Nagios-compatible export.

## Wave 7 — Multi-user and remote hosts

Implement target inventory, execution identities, SSH deployment, remote capability checks, host groups, deployment waves, central PostgreSQL mode, RBAC foundations, and audit expansion.

## Wave 8 — Platform adapters

Add systemd timers first, then evaluate Kubernetes CronJobs and Windows Task Scheduler. Each adapter must pass shared contract tests.

## Wave 9 — Enterprise hardening

Add secrets-provider integrations, approval workflows, SSO, advanced RBAC, high availability, retention policies, backup/restore, compliance exports, signed bundles, and a native Go or Rust agent if operationally justified.

## Wave 10 — Federation

Design only after multiple independent TaskControl domains exist. Add tenant boundaries, regional autonomy, global metadata aggregation, template distribution, event federation, and intermittent-connectivity behaviour.

## Development rule

Each wave should be independently reviewable and should not silently implement later-wave features. Prefer complete vertical slices over broad scaffolding with no working path.
