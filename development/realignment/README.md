# TaskControl Product Realignment Context

> **STATUS: HISTORICAL — provenance only.** This package proposed the cron-backed
> correction. It has been **accepted and reconciled** into the canonical documentation on
> 2026-07-27 by realignment wave R0.
>
> The direction now lives in `../product/`, `../architecture/`, ADRs 0022–0024, and
> `../10_IMPLEMENTATION_BLUEPRINT.md`. **Do not implement from this package** — read it to
> understand *why* the direction changed, then follow the canonical documents.
>
> Excluded from agent context loading, like `../archive/`.

- Status: **Accepted and reconciled** (was: proposed)
- Created after: Wave 3 completion
- Reconciled by: R0, 2026-07-27
- Purpose: record why the product correction was made, and what it replaced

This package captures a proposed realignment of TaskControl. It does not silently override the current Level 0 and Level 1 documentation. The current canonical documents describe an internal scheduler and runtime. The proposed direction instead makes TaskControl a **cron-backed operational task management and asynchronous orchestration platform**.

**That reconciliation is complete.** The implementation freeze has been lifted; the
blueprint identifies R1 as the next wave.

## Core correction

TaskControl must not replace cron or require its own persistent scheduler to keep recurring jobs alive.

Cron remains the trusted scheduling and wake-up mechanism. TaskControl adds value around cron by providing:

1. task authoring without requiring cron knowledge;
2. managed cron installation, update, validation, import, and drift detection;
3. drop-in runnable discovery and registration;
4. operational knowledge, ownership, lifecycle, history, and audit;
5. a REST API for remote task management and asynchronous work submission;
6. a persistent queue processed by short-lived cron-invoked workers;
7. optional runtime helpers for logging, locking, retry, timeout, evidence, and outcome classification.

Wave 3 remains useful as an internal execution capability. It must no longer define the product identity or imply that TaskControl owns scheduling.

## Reading order

1. `01_NORTH_STAR_AND_PRODUCT_BOUNDARY.md`
2. `02_TARGET_USER_WORKFLOWS.md`
3. `03_REFERENCE_ARCHITECTURE.md`
4. `04_CRON_AND_DROP_IN_MODEL.md`
5. `05_REMOTE_API_AND_ASYNC_QUEUE.md`
6. `06_WAVE_3_REUSE_AND_MISALIGNMENTS.md`
7. `07_REALIGNMENT_ACCEPTANCE_CRITERIA.md`
8. `prompts/01_PRODUCT_REALIGNMENT_PR_PROMPT.md`
9. `prompts/02_DOCUMENT_RECONCILIATION_REVIEW_PROMPT.md`
10. `prompts/03_NEXT_IMPLEMENTATION_WAVE_PROMPT.md`

## Non-negotiable constraints

- Cron owns recurring schedule activation.
- TaskControl must continue to provide useful scheduled operation when its web UI or API is unavailable.
- Users should not need to understand cron syntax for ordinary task creation.
- Task definitions remain manageable through files, CLI, web UI, and API.
- Drop-in folders are a first-class authoring and deployment model.
- Remote systems may submit asynchronous work without direct server or crontab access.
- The queue is not a replacement for Kafka, RabbitMQ, Celery, Temporal, or another high-throughput broker.
- The product must not become a LangGraph reproduction or a generic workflow engine without a clear operational-task use case.

## Governance action — completed

R0 superseded the internal-scheduler assumptions across the README, product package,
architecture overview, domain terminology, implementation blueprint, deferred-capability
register, documentation audit, context index, and open questions. ADR 0018 and ADR 0021 were
marked superseded with their reasoning intact, and ADRs 0022, 0023, and 0024 record the new
decisions.

See `../DOCUMENTATION_AUDIT.md` for the file-by-file result.
