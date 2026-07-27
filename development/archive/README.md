# Archive

> **STATUS: ARCHIVED** — nothing in this directory is authoritative.
> Do not load it as implementation context. Do not cite it in a review.

- Lifecycle state: Archived
- Excluded from: the context index reading orders, all agent context loading

## What is here

Documents that were authoritative and have been replaced. They are retained because the reasoning behind an abandoned position is often the fastest way to understand why the current position exists.

Every file carries a banner naming its successor and the reason it was superseded.

## What is not here

- **Deferred capability** lives in `../future/DEFERRED_CAPABILITIES.md`. A capability is not obsolete merely because it is unscheduled; nothing planned was archived.
- **Unresolved decisions** live in `../OPEN_QUESTIONS.md`.
- **External-product-specific material** would live in `../future/`, not here.

## Contents

| File | Superseded by |
| --- | --- |
| `OLD_DEVELOPMENT_README.md` | `../00_CONTEXT_INDEX.md` |
| `00_PRODUCT_VISION.md` | `../product/PRODUCT_VISION.md`, `../product/PRODUCT_PHILOSOPHY.md` |
| `01_SCOPE_AND_OPERATING_LEVELS.md` | `../product/PRODUCT_SCOPE.md`, `../product/PRODUCT_ROADMAP.md` |
| `02_ARCHITECTURE.md` | `../architecture/ARCHITECTURE_OVERVIEW.md` |
| `03_DOMAIN_MODEL.md` | `../domain/`, ADR 0016 |
| `04_TECHNOLOGY_AND_REPOSITORY_STRUCTURE.md` | ADR 0015, `../engineering/repository/10_REPOSITORY_STRUCTURE.md` |
| `05_DELIVERY_ROADMAP.md` | `../product/PRODUCT_ROADMAP.md`, `../10_IMPLEMENTATION_BLUEPRINT.md` |
| `06_ENGINEERING_STANDARDS.md` | `../engineering/` |
| `06_FULL_APPLICATION_BLUEPRINT.md` | `../10_IMPLEMENTATION_BLUEPRINT.md` |
| `00_MASTER_IMPLEMENTATION_PROMPT.md` | `../prompts/IMPLEMENTATION_PROMPT.md` |
| `01_FULL_APPLICATION_GENERATION_PROMPT.md` | `../prompts/IMPLEMENTATION_PROMPT.md` |
| `02_FULL_APPLICATION_ACCEPTANCE_CHECKLIST.md` | per-wave gates in `../10_IMPLEMENTATION_BLUEPRINT.md` |
| `03_DOMAIN_IMPLEMENTATION_PROMPT.md` | `../prompts/IMPLEMENTATION_PROMPT.md`, blueprint Wave 1 |

## Restoring from the archive

Promoting an archived document back to canonical means reversing a decision. It requires an ADR that supersedes the one that archived it. Promoting from `../future/` does not — that is a normal roadmap event.
