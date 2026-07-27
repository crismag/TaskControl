# ADR 0011: Ports and Adapters for External Integrations

- Document level: **1 — Architecture**
- Lifecycle state: Canonical
- Status: Accepted
- Date: 2026-07-26

## Context

TaskControl must integrate with schedulers, executors, secret providers, notification services, monitoring systems, and deployment targets that will change over time.

## Decision

Define technology-neutral ports at application boundaries and implement external systems as adapters. Adapters declare capabilities and translate failures into stable application error categories.

## Rationale

This prevents vendor APIs and SDKs from controlling domain design and enables testing, substitution, and incremental support for new systems.

## Consequences

Interfaces and mapping code require maintenance. Lowest-common-denominator abstractions must be avoided; capability negotiation is preferred where systems differ materially.

## Constraints

- Ports are owned by the consuming application/domain boundary.
- Adapters do not contain product policy.
- Vendor exceptions do not cross adapter boundaries.
- Capabilities, idempotency, timeout, and retry behaviour are explicit.
- Contract tests validate adapters against shared expectations.

## Review triggers

A plugin framework may extend adapter discovery, but it must preserve contracts, isolation, security, and lifecycle management.
