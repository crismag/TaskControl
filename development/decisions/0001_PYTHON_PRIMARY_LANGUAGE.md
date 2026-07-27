# ADR 0001: Python as the Primary Application Language

- Document level: **1 — Architecture**
- Lifecycle state: Canonical
- Status: Accepted
- Date: 2026-07-26

## Context

TaskControl requires orchestration, APIs, CLI tooling, persistence, plugin integration, automation, and future AI-assisted capabilities. The initial team and intended coding agents need one productive language for most server-side behaviour.

## Decision

Use modern Python as the primary language for the control plane, domain, application services, API, CLI, persistence adapters, and initial execution runtime. Use static typing, automated tests, and explicit architectural boundaries.

Go or Rust may later be used for constrained remote agents or performance-sensitive components through stable protocols; they are not part of the initial control plane.

## Rationale

Python offers strong automation and AI ecosystems, mature web and persistence libraries, fast iteration, and alignment with the project's existing skills. A single primary language reduces early integration and operational complexity.

## Consequences

Python performance and packaging limitations must be managed deliberately. CPU-heavy or highly concurrent remote work may eventually move behind language-neutral interfaces. Domain contracts must not depend on Python-specific transport assumptions.

## Implementation constraints

- Supported Python versions must be declared and tested.
- Production code uses type hints.
- Framework-specific types do not enter the domain layer.
- Concurrency is selected from measured needs, not assumed.

## Review triggers

Reconsider when measured workloads cannot meet reliability or performance targets, or remote-agent requirements justify a separate runtime.
