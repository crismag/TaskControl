# Task Analysis and Planning Playbook

## Objective

Convert a feature request, defect, maintenance task, or research result into bounded, reviewable engineering work.

## Analysis sequence

1. Define the observable outcome rather than the desired code change.
2. Identify actors, triggers, inputs, outputs, state transitions, and failure modes.
3. List domain invariants and accepted ADRs that constrain the solution.
4. Distinguish required scope, enabling scope, optional improvements, and non-goals.
5. Identify data model, migration, compatibility, permission, audit, and operations effects.
6. Define acceptance criteria before implementation.
7. Decompose the work into independently verifiable increments.

## Plan format

Each plan should include:

### Outcome

What becomes possible or correct after completion.

### Current behaviour

What the repository does now, supported by code or tests.

### Proposed design

Affected domain objects, use cases, ports, adapters, persistence, delivery surfaces, and event or audit behaviour.

### Change sequence

Order work from inner policy to outer mechanism:

1. domain model and invariants;
2. application use cases and ports;
3. persistence and migrations;
4. integrations and runtime adapters;
5. API, CLI, and UI delivery;
6. tests, documentation, and operational controls.

Not every task requires every layer.

### Verification

Tests, static checks, migration checks, manual scenarios, and failure-path exercises.

### Risks

Compatibility, concurrency, security, performance, data loss, operational, and rollout risks.

### Non-goals

Useful work deliberately excluded from the change.

## Planning rules

- Prefer a small coherent vertical slice over many unfinished layers.
- Do not create abstractions solely for imagined future use.
- Preserve seams documented by accepted ADRs.
- Separate behavioural changes from broad refactors.
- Treat migrations and public contracts as product changes.
- Include rollback or recovery thinking for destructive or operational changes.
- Replan when implementation evidence invalidates a material assumption.

## Ready-to-implement gate

Implementation may start when the outcome, boundaries, acceptance criteria, risks, and first increment are clear enough that another engineer could review the approach before reading the code.