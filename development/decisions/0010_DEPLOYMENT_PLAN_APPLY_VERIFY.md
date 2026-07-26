# ADR 0010: Plan-Apply-Verify Deployment Model

- Document level: **1 — Architecture**
- Lifecycle state: Canonical
- Status: Accepted
- Date: 2026-07-26

## Context

TaskControl will generate and apply scheduler or runtime artefacts. Direct mutation without a reviewable plan creates operational and security risk.

## Decision

All deployments follow an explicit lifecycle: resolve intent, generate an immutable plan, review or approve as policy requires, apply side effects through an adapter, verify actual state, and detect later drift. The rule applies to local cron and future fleet targets.

## Rationale

A consistent lifecycle makes side effects explainable, previewable, auditable, retryable, and extensible across deployment technologies.

## Consequences

Even local deployment requires more structure than directly writing a crontab. This cost is accepted to avoid a disposable local-only architecture.

## Constraints

- Applying requires an immutable plan identifier and content digest.
- Plans contain no resolved secret values.
- Apply operations are idempotent or safely resumable.
- Verification compares intended and observed state.
- Rollback or compensating action is documented per adapter.
- Drift never silently overwrites external changes.

## Review triggers

Adapters may use different mechanics, but none may bypass plan, audit, verification, or permission checks.
