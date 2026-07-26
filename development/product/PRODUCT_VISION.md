# Product Vision

## Mission

Make automated work easy to define, reliable to execute, simple to observe, and safe to operate.

## Vision

TaskControl should become a dependable application that individuals and organisations can use to control scheduled jobs, operational workflows, engineering automation, business processes, application tasks, and other repeatable work from one consistent system.

The product begins as a useful local and single-team utility. It evolves through evidence into a multi-user, multi-host, extensible operations platform without forcing early users to adopt enterprise complexity.

## Product value

TaskControl replaces fragmented combinations of cron entries, shell scripts, custom databases, dashboards, manual runbooks, and disconnected monitoring with one coherent operational model.

Users should be able to answer:

- What work is defined?
- When and why is it eligible to run?
- What is running now?
- What happened during each attempt?
- Did the work achieve the intended outcome?
- What failed, retried, changed, or requires approval?
- Who or what initiated each action?

## Design principles

1. Standalone first — TaskControl must deliver value by itself.
2. General purpose — the core must remain independent of specific domains.
3. Reliable operations — execution truth, retries, timeouts, and outcomes are explicit.
4. Observable by default — state, logs, history, and audit evidence are first-class.
5. Progressive complexity — local usability precedes distributed sophistication.
6. Stable contracts — clients integrate through documented interfaces rather than internals.
7. Human control — consequential actions can be reviewed, approved, paused, cancelled, and audited.
8. Extensible without capture — plugins and adapters extend the product without redefining its core.

## Success criteria for the first product

The first successful release proves that a user can install TaskControl, define a task, schedule or run it, observe its execution, inspect logs and history, understand failure and retry behaviour, and manage it through a usable application interface.

Success does not require KAE, distributed agents, enterprise clustering, or autonomous AI behaviour.