# TaskControl Future Scope

> **STATUS: FUTURE** — this directory describes planned capability intentionally
> outside current TaskControl product scope. Not part of Phase 1 implementation.

- Document level: **0 — Identity (future scope)**
- Lifecycle state: Future
- Governed by: `../product/PRODUCT_SCOPE.md`, `../product/PRODUCT_ROADMAP.md`

## Purpose

Material here is **not obsolete — it is unscheduled.** It describes capability TaskControl intends to have, or capability an external product will build on TaskControl, that is deliberately excluded from the current phase.

Nothing in this directory governs implementation. A coding agent working a blueprint wave does not load it. It exists so that deferring a capability never destroys the thinking behind it, and so that Phase 1 design can be checked against what must remain reachable.

## Distinction from `archive/`

| Directory | Meaning |
| --- | --- |
| `future/` | Correct and wanted, not yet in scope. Will be promoted to canonical when its phase arrives. |
| `archive/` | Superseded or abandoned. Retained for provenance. Will never be promoted. |

Moving a document from `future/` to canonical is a normal roadmap event. Moving one from `archive/` back is a signal that a decision is being reversed and requires an ADR.

## Contents

| File | Covers |
| --- | --- |
| `DEFERRED_CAPABILITIES.md` | Every deferred capability, its origin document, and its phase |

## A note on external products

This directory is where **external-product-specific** implementation and behaviour lives — for example, `future/kae/` would hold KAE's own translation logic and lifecycle if TaskControl ever documents it.

It is **not** where TaskControl's integration surface lives. Ports, public contracts, webhooks, plugin interfaces, and the ecosystem boundary rules are core product surface and stay canonical in `product/` and `domain/`, even when they exist partly to serve an external consumer. TaskControl is designed to support KAE through public interfaces; that design is core, and only KAE's internals would be future.

`future/kae/` does not exist today because the repository contains no KAE-specific implementation material — every current KAE mention is a boundary rule, which is canonical by the test above.
