# ADR 0014: Future Remote Agents Without Premature Distribution

- Document level: **1 — Architecture**
- Lifecycle state: Canonical
- Status: Accepted
- Date: 2026-07-26

## Context

TaskControl may eventually execute work on remote hosts, isolated networks, containers, or high-scale fleets. Building distributed agents immediately would impose security, protocol, upgrade, and observability complexity before requirements are proven.

## Decision

Keep the initial runtime local or control-plane managed, while defining stable executor and deployment ports that can later support remote agents. Do not introduce a remote-agent service, custom protocol, or distributed consensus in the first implementation.

## Rationale

This preserves future direction without paying premature operational cost. Real execution needs can shape the eventual protocol and agent responsibilities.

## Consequences

Initial capabilities are intentionally limited to supported local and adapter-mediated targets. Interfaces must carry durable identifiers, cancellation, timeout, capability, evidence, and idempotency semantics suitable for future remoting.

## Constraints

- The control plane remains authoritative for intent, policy, audit, and outcome.
- Future agents receive scoped work and credentials, not unrestricted database access.
- Agent communication must be authenticated, encrypted, replay-safe, and versioned.
- Offline, duplicate, delayed, and unknown-result scenarios must be modelled explicitly.
- Go or Rust may be selected for agents through a future ADR based on measured requirements.

## Review triggers

Create a new ADR when real use cases define connectivity, scale, trust boundaries, packaging, upgrade, and failure-recovery requirements.
