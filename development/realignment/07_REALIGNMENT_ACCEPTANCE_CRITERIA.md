# Product Realignment Acceptance Criteria

- Status: Proposed
- Purpose: define when documentation is clear enough for implementation to resume

## R0 goal

Create one canonical, internally consistent product and architecture direction that preserves completed engineering work where useful while replacing the internal-scheduler-first product identity.

## Required canonical changes

The realignment is incomplete until all affected authoritative documents agree that:

1. TaskControl is cron-backed and does not replace cron.
2. Cron owns recurring activation.
3. TaskControl owns task lifecycle, cron management, operational knowledge, remote API contracts, and a bounded asynchronous queue.
4. The web/API control plane is not required to stay alive for already-deployed recurring jobs.
5. Drop-in runnable packages are first-class.
6. Wave 3 is a supporting execution service, not the product centre.
7. Remote orchestration is primarily asynchronous and durable.
8. The first queue is intentionally simpler than a broker or generic workflow engine.
9. Any scheduler abstraction exists to manage external scheduler targets, with cron as the first production adapter.

## Documents that must be reconciled

At minimum:

- `/README.md`
- `development/00_CONTEXT_INDEX.md`
- `development/product/README.md`
- `development/product/PRODUCT_VISION.md`
- `development/product/PRODUCT_SCOPE.md`
- `development/product/PRODUCT_PHILOSOPHY.md`
- `development/product/USERS_AND_USE_CASES.md`
- `development/product/USER_JOURNEYS.md`
- `development/product/INTEGRATION_STRATEGY.md`
- `development/product/PRODUCT_ROADMAP.md`
- `development/architecture/ARCHITECTURE_OVERVIEW.md`
- relevant domain handbooks
- relevant engineering rules
- `development/10_IMPLEMENTATION_BLUEPRINT.md`
- `development/future/DEFERRED_CAPABILITIES.md`
- `development/DOCUMENTATION_AUDIT.md`
- `development/OPEN_QUESTIONS.md`
- `development/decisions/0018_INTERNAL_SCHEDULER_BEFORE_ARTEFACT_DEPLOYMENT.md`
- `development/decisions/README.md`

The PR may find additional affected documents and must update them in the same reconciliation.

## ADR requirements

Create a new ADR that explicitly:

- records the previous scheduler-first decision;
- explains why it no longer matches product intent;
- supersedes ADR 0018 where necessary;
- establishes cron-backed recurring activation;
- distinguishes control plane, cron management, queue worker, and execution services;
- states the availability and failure-isolation principles;
- defines what is intentionally unresolved.

Do not simply edit an accepted ADR to erase history.

## Blueprint requirements

The revised blueprint must:

- mark Waves 0–3 as completed and retained pending compatibility review;
- stop the old Wave 4 sequence;
- introduce realignment and migration work before new product features;
- define a cron-backed vertical slice early;
- add drop-in discovery and managed cron artefacts;
- add API-submitted work items and a cron-woken worker;
- sequence operational knowledge, import/adoption, and drift detection;
- delay complex pipelines, remote workers, and generic DAG behaviour.

## First post-realignment milestone

A useful first milestone should prove the complete user value chain:

```text
Create task without cron syntax
        -> validate
        -> plan managed cron change
        -> apply
        -> cron activates task
        -> Wave 3 execution service records outcome
        -> inspect task and attempt through API/CLI
```

A second vertical slice should prove:

```text
Remote client submits work item
        -> durable accepted response
        -> cron wakes bounded worker
        -> worker safely claims and processes item
        -> caller inspects terminal or retry status
```

## Documentation quality gates

- One definition of product identity.
- One architecture diagram for the target system.
- One roadmap and one implementation sequence.
- No active document describes an internal scheduler as the required Phase 1 scheduling engine.
- No active document presents cron management as merely distant future scope.
- No duplicate or contradictory execution, queue, or schedule terminology.
- Every superseded statement is updated or archived with provenance.
- Context index and documentation audit match the final file state.
- Prompts instruct coding agents to verify canonical sources rather than treating this proposal package as permanent authority.

## Implementation freeze exit

Implementation may resume only when the realignment PR is merged and its revised blueprint identifies the next bounded wave with acceptance tests.
