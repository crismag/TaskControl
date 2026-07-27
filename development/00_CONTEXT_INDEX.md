# TaskControl Context Index

- Document level: **entry point**
- Status: Authoritative
- Last reconciled: 2026-07-26

This is the only documented starting point for TaskControl. Every contributor and coding agent begins here.

No other document publishes a repository-wide reading order or the precedence ladder. A package `README.md` may order its own files; it may not rank itself against other packages.

## What TaskControl is

TaskControl is a standalone, general-purpose application for defining, scheduling, executing, observing, and governing automated work. It is useful on its own, without any external platform. See `product/PRODUCT_VISION.md`.

## Current state of the repository

**Wave 0 complete.** The project installs, lints, type-checks, and tests green, and exposes
version and health through the CLI and the API. No product behaviour beyond that yet.

The next action is Wave 1 (Domain core) of `10_IMPLEMENTATION_BLUEPRINT.md`. High-level product and architecture documentation is frozen: changes at Level 0 or Level 1 now require an ADR and an explicit supersession analysis (ADR 0017).

## Documentation levels

Higher levels govern lower ones. A lower level may refine a higher one; it may never redefine it. Every document declares its level in its header.

| Level | Name | Answers | Where |
| --- | --- | --- | --- |
| 0 | Identity | Why TaskControl exists, for whom, what is out of scope | `/README.md`, `product/` |
| 1 | Architecture | Boundaries, concepts, decisions, engineering rules | `architecture/`, `domain/`, `decisions/`, `engineering/` |
| 2 | Blueprint | Given today's repository, what we build next | `10_IMPLEMENTATION_BLUEPRINT.md` |
| 3 | Specifications | How one wave or capability is built and accepted | `specifications/`, `ai-operations/`, `prompts/` |
| 4 | Source | The implementation | `/src`, `/apps`, `/web`, `/tests` |
| — | Future | Correct and wanted, deliberately out of current scope | `future/` |
| — | Historical | Superseded or abandoned text, retained for provenance | `archive/` |

## Precedence ladder

When two documents disagree, apply in order:

1. **Level 0 product constraints** — `product/PRODUCT_SCOPE.md`, `product/PRODUCT_VISION.md`
2. **Accepted ADRs** — `decisions/`
3. **Domain handbook** — `domain/`
4. **Architecture** — `architecture/`
5. **Engineering governance** — `engineering/`
6. **Blueprint and specifications** — `10_IMPLEMENTATION_BLUEPRINT.md`, `specifications/`, `prompts/`

`archive/` and `future/` never participate: the first is superseded, the second is out of scope. If applying this ladder is ever necessary, the losing document is defective and must be corrected in the same pull request — see the supersession rule in ADR 0017.

## Single-authority map

Exactly one document answers each of these. No other document may restate the answer.

| Question | Sole authority |
| --- | --- |
| Why does the product exist, and for whom? | `product/PRODUCT_VISION.md`, `product/USERS_AND_USE_CASES.md` |
| What is in and out of scope? | `product/PRODUCT_SCOPE.md` |
| What is deferred, and to when? | `future/DEFERRED_CAPABILITIES.md` |
| What is the delivery order? | `product/PRODUCT_ROADMAP.md` (phases) → `10_IMPLEMENTATION_BLUEPRINT.md` (waves) |
| What is the directory tree? | `engineering/repository/10_REPOSITORY_STRUCTURE.md` (per ADR 0015) |
| What are the execution states and outcomes? | ADR 0016 |
| What does a domain concept mean? | `domain/` |
| How must code be written and reviewed? | `engineering/` |
| How does an agent work a task? | `ai-operations/` |
| What do we build next? | `10_IMPLEMENTATION_BLUEPRINT.md` |

## Reading order

### For implementation work

1. This index.
2. `10_IMPLEMENTATION_BLUEPRINT.md` — the current wave.
3. `product/PRODUCT_SCOPE.md` — the Phase 1 boundary.
4. The `domain/` files naming the concepts in your wave.
5. The ADRs listed by your wave.
6. `engineering/` standards for the layer you are touching.
7. `ai-operations/` playbook matching your activity.

### For product or architecture review

1. This index.
2. `product/` in the order given by `product/README.md`.
3. `architecture/ARCHITECTURE_OVERVIEW.md`.
4. `domain/` in the order given by `domain/README.md`.
5. `decisions/README.md`.

## File map

### Level 0 — Identity

| File | Purpose |
| --- | --- |
| `/README.md` | Public product description and entry point |
| `product/README.md` | Product package index and invariant |
| `product/PRODUCT_VISION.md` | Mission, value, principles, success criteria |
| `product/PRODUCT_SCOPE.md` | Owned capabilities, non-goals, first-release boundary |
| `product/PRODUCT_PHILOSOPHY.md` | Design philosophy and the product test |
| `product/USERS_AND_USE_CASES.md` | Target users and representative workloads |
| `product/USER_JOURNEYS.md` | Concrete journeys used to test abstractions |
| `product/ECOSYSTEM_BOUNDARIES.md` | Relationship to KAE and other external systems |
| `product/INTEGRATION_STRATEGY.md` | Public integration surfaces and contract rules |
| `product/PRODUCT_ROADMAP.md` | Phases 1–4 |


### Future scope — not implementation context

| File | Purpose |
| --- | --- |
| `future/README.md` | What Future means and how it differs from Archived |
| `future/DEFERRED_CAPABILITIES.md` | Every deferred capability, its origin, and its phase |

### Level 1 — Architecture

| File | Purpose |
| --- | --- |
| `architecture/ARCHITECTURE_OVERVIEW.md` | Style, layers, runtime flow, topology, boundaries |
| `domain/README.md` … `domain/09_*.md` | The domain handbook (11 files) |
| `decisions/README.md`, `decisions/00NN_*.md` | ADRs 0001–0019 |
| `engineering/README.md` and subdirectories | Charter, laws, structure, dependency rules, standards, quality, governance, AI policy |

### Level 2 — Blueprint

| File | Purpose |
| --- | --- |
| `10_IMPLEMENTATION_BLUEPRINT.md` | Ordered waves, file-level outputs, acceptance gates |

### Level 3 — Specifications

| File | Purpose |
| --- | --- |
| `ai-operations/README.md` … `11_*.md` | Agent operating playbooks (12 files) |
| `prompts/IMPLEMENTATION_PROMPT.md` | The single agent prompt |
| `specifications/` | Per-wave specifications, created as waves begin |

### Supporting

| File | Purpose |
| --- | --- |
| `OPEN_QUESTIONS.md` | Unresolved decisions blocking or shaping future work |
| `DOCUMENTATION_AUDIT.md` | Lifecycle state and reason for every file |
| `archive/README.md` | Index of superseded documents and what replaced them |

## Rules for changing this repository

1. Identify what your change supersedes before you write it. State it in the pull request.
2. Edit the document that is now wrong. Do not add a document that disagrees with it.
3. Classify every document you touch as Canonical, Superseded, Archived, Future, or Open decision (ADR 0017).
4. Migrate deferred capability to `future/DEFERRED_CAPABILITIES.md` and unresolved choices to `OPEN_QUESTIONS.md` **before** archiving anything.
5. Move superseded text to `archive/` with its banner. Do not leave it in place.
6. Update this index and `DOCUMENTATION_AUDIT.md` in the same pull request.
7. A change to Level 0 or Level 1 requires an ADR.

Discovering a conflict is never a reason to write a new document. Fix the document that is wrong.
