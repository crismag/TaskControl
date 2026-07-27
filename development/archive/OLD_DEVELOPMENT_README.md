> **STATUS: SUPERSEDED** — replaced by `development/00_CONTEXT_INDEX.md`.
>
> Retained for historical reasoning. **Do not use for new implementation.**
>
> Superseded: 2026-07-26. Reason: Its reading order led readers through superseded documents before current ones and omitted 14 files. Reading order and precedence are now published only by the context index (ADR 0017).

---

# TaskControl Development Context

This directory is the authoritative development workspace for human and AI-assisted implementation of TaskControl.

## Product identity

TaskControl is a standalone, general-purpose application for task orchestration, scheduling, execution, monitoring, and operational governance. It must be useful without KAE, an AI framework, or any other external platform.

KAE may use TaskControl through public interfaces, but TaskControl must not depend on KAE. The same rule applies to every domain-specific consumer.

## Purpose

TaskControl is intended to scale from a practical single-user automation utility to a multi-user and multi-host operations platform. The first priority is a functional base application that can define, schedule, run, observe, and manage tasks reliably.

The development context is split into focused files so a contributor or coding agent can load only the material required for a development wave while preserving product and architectural coherence.

## Recommended reading order

1. `product/README.md`
2. `00_PRODUCT_VISION.md`
3. `01_SCOPE_AND_OPERATING_LEVELS.md`
4. `02_ARCHITECTURE.md`
5. `03_DOMAIN_MODEL.md`
6. `04_TECHNOLOGY_AND_REPOSITORY_STRUCTURE.md`
7. `05_DELIVERY_ROADMAP.md`
8. `06_ENGINEERING_STANDARDS.md`
9. `engineering/README.md`
10. `decisions/README.md`
11. `ai-operations/README.md`
12. applicable implementation prompts and wave documents

## Core implementation decision

The first reference implementation uses Python for the control plane, domain engine, CLI, local runtime, API, adapters, and orchestration. TypeScript is reserved for the web interface. Protocols, schemas, task bundles, and worker boundaries must remain language-neutral so other runtimes can be introduced later without redesigning the product.

## Product boundary rules

- TaskControl owns task definition, scheduling, execution, dependencies, retries, approvals, monitoring, history, audit, and extension contracts.
- TaskControl does not own requirements engineering, knowledge acquisition, semantic memory, AI reasoning, research, or software-design generation.
- AI workflows are supported workloads, not the product identity.
- KAE is an external consumer and integration example, not an internal subsystem.
- Public interfaces must remain usable by scripts, people, services, business applications, engineering systems, and AI-enabled clients equally.

## Context usage rules

- Treat task definitions as the source of truth, not generated cron lines or scripts.
- Separate trigger, eligibility, execution, attempts, deployment, monitoring, and observed outcomes.
- Preserve a path from local operation to multi-user, multi-host, multi-platform, and enterprise deployment.
- Do not implement enterprise complexity prematurely; define stable extension points instead.
- Generated artefacts must be reproducible, reviewable, and traceable to their source definitions.
- Every implementation wave must include tests, documentation, migration notes, and a clear completion report.

## Development context lifecycle

Context documents may evolve as decisions are validated. Changes that alter product boundaries, architecture, schemas, identifiers, security boundaries, or runtime behaviour should be recorded in an architecture decision record under `development/decisions/`.
