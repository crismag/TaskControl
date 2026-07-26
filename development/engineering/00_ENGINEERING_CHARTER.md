# Engineering Charter

## Mission

Build TaskControl as a dependable operational execution platform whose behaviour is understandable, reviewable, testable, secure, and evolvable.

## Scope

This charter governs architecture-preserving implementation, maintenance, refactoring, testing, documentation, release preparation, and AI-assisted development.

## Engineering objectives

1. Correctly represent domain rules and state transitions.
2. Prevent framework and infrastructure concerns from controlling the domain.
3. Make operational behaviour observable and diagnosable.
4. Preserve compatibility deliberately rather than accidentally.
5. Keep execution, deployment, permission, configuration, and audit decisions explainable.
6. Enable incremental delivery without normalising architectural shortcuts.
7. Leave durable knowledge for future contributors and agents.

## Quality dimensions

Every meaningful change is evaluated for:

- functional correctness;
- reliability and recoverability;
- security and least privilege;
- observability;
- maintainability;
- extensibility;
- performance proportional to measured need;
- portability;
- migration safety;
- documentation completeness.

## Engineering levels

### Level 1 — Vision

Why does the capability exist and what outcome must it produce?

### Level 2 — Architecture and domain

Which bounded contexts, aggregates, services, policies, and interfaces own the behaviour?

### Level 3 — Engineering design

How will dependencies, persistence, errors, security, tests, and observability be handled?

### Level 4 — Implementation

Only after Levels 1–3 are understood should code be written.

## Decision priorities

When trade-offs conflict, prefer:

1. correctness and safety;
2. domain integrity;
3. architectural boundaries;
4. clarity and explainability;
5. backward compatibility;
6. maintainability and testability;
7. measured performance;
8. implementation speed.

## Exceptions

An exception must be explicit, narrow, reviewable, time-bounded where possible, and accompanied by one of:

- an ADR;
- a tracked technical-debt item;
- a documented migration plan.

Undocumented exceptions are defects.
