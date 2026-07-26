# ADR 0008: Separate Execution, Attempt, and Outcome

- Document level: **1 — Architecture**
- Lifecycle state: Canonical
- Status: Accepted
- Date: 2026-07-26

## Context

A logical run may be retried, cancelled, timed out, fail before process start, or exit successfully while violating the expected operational result.

## Decision

Model Execution as the logical requested run, Attempt as one concrete execution try, and Outcome Evaluation as evidence-based validation of the intended result.

## Rationale

Combining these concepts would make retries, diagnosis, reporting, and success semantics ambiguous. Process completion and operational success are not equivalent.

## Consequences

The model is more detailed, but it preserves reliable histories and enables precise failure classification.

## Constraints

- One Execution may contain zero or more Attempts.
- Each Attempt records immutable timing, runner, exit, termination, and evidence references.
- Exit code zero does not automatically make the Execution successful.
- Skipped triggers do not create synthetic Attempts.
- Unknown infrastructure state remains distinct from known failure.

## Review triggers

Outcome evaluation may gain richer rule engines, but the separation of logical run, physical attempts, and business outcome remains binding.
