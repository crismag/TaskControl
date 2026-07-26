# TaskControl AI Development Operations

- Document level: **3 — Specifications**
- Lifecycle state: Canonical

## Purpose

This package defines repeatable operating procedures for AI coding agents working on TaskControl. It converts the repository's vision, domain handbook, engineering governance, and ADRs into executable development workflows.

These playbooks apply to Claude, Codex, ChatGPT, local models, and future orchestrated agents. They do not lower the review standard for generated work. AI-produced changes must satisfy the same architecture, security, testing, documentation, and operational requirements as human-produced changes.

## Mandatory context order

Before modifying code, an agent must read the relevant material in this order:

1. Product vision and current roadmap.
2. Domain handbook and invariants.
3. Architecture and application blueprint.
4. Engineering governance.
5. Applicable accepted ADRs.
6. The relevant playbook in this package.
7. Existing implementation and tests.

A prompt or ticket never overrides accepted repository policy. Conflicts must be surfaced explicitly.

## Operating model

Every substantial task follows this lifecycle:

1. **Orient** — understand the repository and requested outcome.
2. **Constrain** — identify domain rules, ADRs, dependencies, and non-goals.
3. **Plan** — propose an incremental, testable implementation sequence.
4. **Implement** — make the smallest coherent change.
5. **Verify** — run tests and inspect failure paths.
6. **Review** — perform structured architecture, domain, security, and operations review.
7. **Document** — update affected knowledge and record assumptions.
8. **Handoff** — provide evidence, remaining risks, and next work.

## Playbooks

- `01_REPOSITORY_ORIENTATION.md` — establish trustworthy context before coding.
- `02_TASK_ANALYSIS_AND_PLANNING.md` — transform a request into bounded engineering work.
- `03_INCREMENTAL_IMPLEMENTATION.md` — implement without architectural drift.
- `04_TESTING_AND_VERIFICATION.md` — prove behaviour and failure handling.
- `05_STRUCTURED_REVIEW.md` — run multi-perspective self-review.
- `06_SECURITY_AND_OPERATIONS_REVIEW.md` — assess production-facing risks.
- `07_DOCUMENTATION_AND_TRACEABILITY.md` — keep knowledge aligned with code.
- `08_PULL_REQUEST_AND_HANDOFF.md` — produce reviewable changes and durable handoffs.
- `09_REFACTORING_AND_MAINTENANCE.md` — improve structure without hiding behaviour changes.
- `10_AI_PROMPT_CONTRACT.md` — standard contract for task-specific agent prompts.
- `11_AGENT_FAILURE_AND_ESCALATION.md` — handle ambiguity, blocked work, and unsafe assumptions.

## Required outputs

Unless the task is trivial, an AI agent must leave:

- a concise implementation plan;
- explicit assumptions and non-goals;
- changed code and tests;
- commands run and their results;
- documentation updates or a justified statement that none are required;
- known risks and deferred items;
- a clear next-step recommendation.

## Prohibited behaviour

Agents must not:

- invent requirements to fill material gaps;
- bypass domain invariants for convenience;
- move business logic into API, CLI, ORM, UI, or integration code;
- rewrite accepted ADR history;
- mix unrelated cleanup into feature changes;
- claim tests passed when they were not run;
- silently weaken validation, permissions, audit, or observability;
- introduce distributed infrastructure before documented need;
- hide uncertainty behind confident language.

## Relationship to implementation playbooks

This package defines **how an AI engineer works**. Future implementation-wave playbooks define **what TaskControl should build and in what sequence**.
