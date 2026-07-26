# AI Engineering Playbook

- Document level: **1 — Architecture**
- Lifecycle state: Canonical

This playbook governs Claude, Codex, ChatGPT, and other coding agents contributing to TaskControl.

## Before coding

1. Read relevant files under `development/vision/`, `development/architecture/`, `development/domain/`, and `development/engineering/`.
2. Inspect the current repository rather than assuming scaffolding or contracts exist.
3. Restate the requested outcome, affected bounded contexts, and acceptance conditions.
4. Identify dependency boundaries, persistence impact, API/CLI/UI impact, security requirements, and operational failure modes.
5. Separate confirmed requirements from assumptions.
6. Produce a small implementation plan ordered by dependency and risk.

## During implementation

- Implement through domain and application contracts before transports.
- Reuse established vocabulary and patterns.
- Keep changes cohesive and reviewable.
- Add tests alongside behaviour.
- Preserve error causes and classify failures precisely.
- Keep configuration explicit and deterministic.
- Add logging, metrics, audit, and redaction at the relevant boundaries.
- Do not replace unfinished work with mocks and claim completion.
- Do not remove abstractions merely because only one adapter currently exists.
- Do not rewrite unrelated code to make the local task easier.

## When requirements are incomplete

Prefer the safest architecture-compatible interpretation. Record material assumptions in the pull request or `IMPLEMENTATION_STATUS.md`. Do not silently invent permanent product behaviour.

When blocked by missing access, external services, or unavailable decisions:

- complete all unblocked work;
- leave interfaces and tests where possible;
- document the exact blocker;
- identify the next concrete action;
- do not present placeholders as finished implementation.

## Self-review before completion

Check:

- domain and state semantics;
- forbidden dependencies;
- duplicate logic;
- transaction and idempotency behaviour;
- timeout, retry, cancellation, and partial failure;
- authentication, authorisation, secrets, and audit;
- logging, metrics, correlation, and diagnosis;
- tests for success and failure paths;
- migration and compatibility effects;
- documentation and implementation status.

## Output expectations

An AI change summary should identify:

1. what was implemented;
2. important design decisions;
3. files or modules changed;
4. tests and checks performed;
5. assumptions and limitations;
6. remaining work;
7. whether the definition of done is satisfied.

## Prohibited completion behaviour

An agent must not:

- claim tests passed without running them;
- claim a full application exists when only scaffolding was created;
- hide failing checks;
- fabricate external integration results;
- bypass architecture to satisfy a superficial acceptance test;
- delete existing requirements or documentation to remove conflicts;
- leave silent TODOs for critical correctness or security work.
