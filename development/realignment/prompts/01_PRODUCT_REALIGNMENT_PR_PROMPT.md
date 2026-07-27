# Prompt — Product Realignment PR

Use this prompt with Claude Code, Codex, or another repository-capable coding agent.

## Assignment

Create one documentation-only pull request that reconciles TaskControl around the proposed cron-backed direction in `development/realignment/`.

Do not implement new product code in this PR.

## Required preparation

1. Read `development/00_CONTEXT_INDEX.md` and follow its governance rules.
2. Read every file under `development/realignment/` before editing canonical documents.
3. Inspect the current README, product package, architecture, domain handbook, decisions, implementation blueprint, future register, open questions, and documentation audit.
4. Search the entire repository for assumptions involving internal scheduler ownership, persistent scheduler processes, crontab deferral, runtime-first identity, and `taskctl execute` as a primary user journey.
5. Inspect Wave 3 source and tests only enough to describe retained and potentially misaligned capabilities accurately. Do not refactor code in this PR.

## Product direction to establish

TaskControl is a cron-backed operational task management and asynchronous orchestration platform.

- Cron remains the recurring activation mechanism.
- TaskControl manages task definitions, human-friendly schedules, cron artefacts, drop-ins, operational knowledge, remote APIs, durable queued work, outcomes, and audit.
- The web/API control plane is not required to remain alive for already-deployed recurring jobs.
- Short-lived TaskControl execution services may be invoked by cron, queue workers, or explicit run-now operations.
- Remote systems submit approved task types or work items; they do not gain unrestricted remote shell execution.
- Queue processing is bounded and cron-woken, not a high-throughput broker or general workflow engine.

## Required changes

1. Create a new accepted ADR that records and supersedes the internal-scheduler-first decision where needed. Preserve decision history.
2. Reconcile all affected Level 0 and Level 1 documents.
3. Rewrite the implementation blueprint to stop the old Wave 4 progression and introduce the realigned sequence.
4. Update the context index and documentation audit.
5. Move capabilities between current and future scope as required.
6. Update open questions with unresolved implementation choices rather than inventing answers.
7. Mark Waves 0–3 as completed under the previous direction and retained pending compatibility review.
8. Keep `development/realignment/` as proposal/provenance material or archive it according to repository governance after canonical reconciliation. Do not leave two competing authorities.

## Required next-wave sequence

The revised blueprint should begin with bounded work similar to:

- R0: canonical product and architecture reconciliation;
- R1: Wave 3 compatibility review and terminology cleanup;
- R2: managed cron artefact vertical slice;
- R3: drop-in discovery and registration;
- R4: operational knowledge and drift/import foundations;
- R5: asynchronous work-item API and cron-woken worker.

You may refine this sequence, but cron-backed user value must be proven before expanding generic workflow features.

## Prohibited actions

- Do not delete Wave 3 implementation merely because the product changed.
- Do not continue the old Wave 4 implementation.
- Do not introduce an internal always-on scheduler under a new name.
- Do not describe cron as a temporary legacy adapter.
- Do not claim that queue processing replaces RabbitMQ, Kafka, Celery, or Temporal.
- Do not create duplicate vision documents instead of correcting canonical ones.
- Do not silently edit accepted ADR history.
- Do not add unsupported product promises.

## Deliverables

- coherent canonical documentation;
- new superseding ADR;
- updated context index;
- updated documentation audit;
- revised implementation blueprint;
- explicit supersession analysis in the PR description;
- list of source-code assumptions requiring later review;
- no source-code changes except unavoidable documentation metadata or test fixtures explicitly justified.

## Validation

Before completing:

1. Search again for contradictory scheduler-first language.
2. Confirm every active document agrees on cron ownership.
3. Confirm cron management and drop-ins are no longer deferred out of the first useful product path.
4. Confirm the queue is asynchronous, durable, bounded, and cron-woken.
5. Confirm the context index points agents to one authoritative direction.
6. Run repository documentation checks and `make check` if the repository requires it for documentation PRs.

## PR title

`docs: realign TaskControl as a cron-backed operational automation platform`
