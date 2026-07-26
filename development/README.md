# TaskControl Development Context

This directory is the authoritative development workspace for AI-assisted and human implementation of TaskControl.

## Purpose

TaskControl is intended to scale from a single-user scheduled-task manager to a federated enterprise operations platform. The development context is intentionally split into multiple focused files so Codex, Claude, or another capable coding agent can load only the context required for a development wave while preserving architectural coherence.

## Recommended reading order

1. `00_PRODUCT_VISION.md`
2. `01_SCOPE_AND_OPERATING_LEVELS.md`
3. `02_ARCHITECTURE.md`
4. `03_DOMAIN_MODEL.md`
5. `04_TECHNOLOGY_AND_REPOSITORY_STRUCTURE.md`
6. `05_DELIVERY_ROADMAP.md`
7. `06_ENGINEERING_STANDARDS.md`
8. `prompts/00_MASTER_IMPLEMENTATION_PROMPT.md`

## Core implementation decision

The first reference implementation uses Python for the control plane, domain engine, CLI, local runtime, API, adapters, and orchestration. TypeScript is reserved for the web interface. Protocols, schemas, task bundles, and agent boundaries must remain language-neutral so a compiled Go or Rust host agent may be introduced later without redesigning the product.

## Context usage rules

- Treat task definitions as the source of truth, not generated cron lines or scripts.
- Separate trigger, run conditions, execution, deployment, monitoring, and observed outcomes.
- Preserve a path from local-only operation to multi-user, multi-host, multi-platform, enterprise, and federated operation.
- Do not implement enterprise complexity prematurely; define stable extension points instead.
- Generated artefacts must be reproducible, reviewable, and traceable to their source definitions.
- Every implementation wave must include tests, documentation, migration notes, and a clear completion report.

## Development context lifecycle

Context documents may evolve as decisions are validated. Changes that alter architecture, schemas, identifiers, security boundaries, or runtime behaviour should be recorded in an architecture decision record under `development/decisions/`.
