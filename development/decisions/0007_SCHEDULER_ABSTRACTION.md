# ADR 0007: Scheduler Abstraction and Candidate Triggers

- Status: Accepted
- Date: 2026-07-26

## Context

TaskControl must support local cron initially while remaining capable of integrating systemd timers, Kubernetes CronJobs, enterprise schedulers, and future native scheduling.

## Decision

Represent scheduling through domain schedules and scheduler adapter ports. A scheduler emits a candidate trigger; TaskControl then evaluates calendars, conditions, policies, idempotency, and concurrency before creating an execution.

## Rationale

This separates time calculation from business eligibility and prevents external schedulers from becoming the source of truth for execution semantics.

## Consequences

Trigger handling requires durable identity and deduplication. Adapter capabilities differ and must be declared rather than hidden.

## Constraints

- Candidate trigger identity is stable and idempotent.
- Skipped eligibility is recorded separately from successful execution.
- Scheduler adapters do not own TaskControl domain state.
- Misfire and catch-up policies are explicit.

## Review triggers

A native scheduler may be introduced when distributed timing, scale, or resilience requirements are proven.
