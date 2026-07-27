# ADR 0015: Canonical Repository Layout

- Document level: **1 — Architecture**
- Lifecycle state: Canonical
- Status: Accepted
- Date: 2026-07-26
- Owners: TaskControl maintainers
- Supersedes: Layout sections of `development/archive/04_TECHNOLOGY_AND_REPOSITORY_STRUCTURE.md` and `development/archive/06_FULL_APPLICATION_BLUEPRINT.md`
- Superseded by: ADR 0019, for the `apps/` placement only; the rest stands
- Related documents: `development/00_CONTEXT_INDEX.md`, `development/engineering/repository/10_REPOSITORY_STRUCTURE.md`, `development/engineering/repository/11_DEPENDENCY_RULES.md`, ADR 0003, ADR 0011

## Context

Four documents independently proposed a source layout, and no two agreed:

| Document | `apps/` | `ports/` | Adapter location | Web location |
| --- | --- | --- | --- | --- |
| `04_TECHNOLOGY_AND_REPOSITORY_STRUCTURE.md` | no | no | `src/taskcontrol/adapters/` | `web/` |
| `06_FULL_APPLICATION_BLUEPRINT.md` | yes | no | top-level `adapters/` | `apps/web/` |
| `engineering/repository/10_REPOSITORY_STRUCTURE.md` | yes | yes | `src/taskcontrol/adapters/` | `web/` |
| `domain/09_DOMAIN_IMPLEMENTATION_CONTRACT.md` | no | `application/ports/` | `infrastructure/*` | not stated |

A coding agent following the repository's own instruction to treat all development context as authoritative could not choose without violating something. Layout is the first decision any implementation makes and every later file placement inherits it, so it must have exactly one answer.

## Decision drivers

- Dependency direction must be visible in the tree, not only in prose.
- Composition roots must be separable from transport code so a worker process can be added without restructuring.
- Ports must be discoverable as consumer-owned contracts (ADR 0011).
- The layout must survive the later addition of remote workers (ADR 0014) without a rename.
- Packaging must support `pip install taskcontrol` with a `src/` layout.

## Considered options

### Option A — `engineering/repository/10` shape

`apps/` composition roots, `src/taskcontrol/{domain,application,ports,adapters,api,cli,infrastructure}`, top-level `web/`.

Strengths: explicit `ports/`; single installable package; entry points separated from transport. Weaknesses: `apps/` and `src/taskcontrol/api` can look redundant until the distinction is documented.

### Option B — Blueprint shape

Top-level `adapters/` and `apps/web/`.

Strengths: adapters are prominent. Weaknesses: adapters outside the installed package are not importable after `pip install`; the web client becomes a Python-adjacent directory; two languages share `apps/`.

### Option C — `domain/09` shape

`infrastructure/{persistence,executors,schedulers,...}` with no `adapters/` directory.

Strengths: fewer concepts. Weaknesses: conflates process bootstrapping with external-system translation, which ADR 0011 deliberately separates.

## Decision

Adopt **Option A**. The canonical layout is:

> **Corrected by ADR 0019.** The tree below shows `apps/` at top level. That placement is wrong:
> a top-level `apps/` is not present in an installed wheel, so console scripts and ASGI factories
> cannot resolve from it. Composition roots live at `src/taskcontrol/apps/`. Everything else in this
> ADR stands. `engineering/repository/10_REPOSITORY_STRUCTURE.md` carries the corrected tree.

```text
TaskControl/
├── pyproject.toml
├── README.md
├── Makefile
├── .env.example
├── src/taskcontrol/
│   ├── apps/                  # composition roots only: wiring, settings, process startup
│   ├── domain/                # entities, value objects, policies, pure decisions
│   ├── application/           # use cases, commands, queries, orchestration
│   ├── ports/                 # interfaces required by domain and application
│   ├── adapters/              # implementations of ports against external technology
│   ├── api/                   # HTTP routers and transport schemas
│   ├── cli/                   # CLI transport
│   ├── infrastructure/        # configuration, logging, engine creation, wiring helpers
│   └── common/                # genuinely cross-cutting stable utilities
├── web/                       # React + TypeScript client
├── migrations/                # Alembic
├── schemas/                   # exported JSON Schema for portable definitions
├── examples/
├── tests/{unit,integration,contract,end_to_end}/
├── docs/
└── development/               # authoritative project knowledge (see 00_CONTEXT_INDEX.md)
```

`apps/` contains **only** composition: build settings, configure logging, instantiate adapters, start a process. `src/taskcontrol/api/` and `src/taskcontrol/cli/` contain the routers and commands those roots mount. Business rules appear in neither.

`development/engineering/repository/10_REPOSITORY_STRUCTURE.md` is the single normative statement of directory responsibilities. No other document may restate the tree; documents that need it link to that file.

## Rationale

Option A is the only proposal that keeps every runtime artefact inside one installable package while still separating the four distinct responsibilities the engineering laws require: composition, transport, application, and domain. It also names `ports/` as a first-class directory, which makes ADR 0011 checkable by a static import test rather than by review discipline.

## Consequences

### Positive

- One answer to "where does this file go".
- Forbidden imports become mechanically testable (`tests/unit/test_architecture.py`).
- Adding `apps/worker/` in Phase 3 requires no restructuring.

### Negative or accepted trade-offs

- The `apps/api` versus `src/taskcontrol/api` distinction must be explained to new contributors.
- A `src/` layout requires editable installs during development.

### Risks and mitigations

- Risk: `common/` becomes a dumping ground — mitigation: the placement rule in `10_REPOSITORY_STRUCTURE.md` plus review attention.
- Risk: adapters grow domain logic — mitigation: contract tests and the architecture import test.

## Implementation constraints

- `src/taskcontrol/domain/` may import only the standard library and approved pure libraries.
- No module under `src/taskcontrol/domain/` or `src/taskcontrol/application/` may import FastAPI, Typer, SQLAlchemy, or a vendor SDK.
- `apps/` modules contain no branching business rules.
- Adapters import ports; ports never import adapters.

## Validation

An architecture test enumerates the import graph and fails on any forbidden edge listed in `engineering/repository/11_DEPENDENCY_RULES.md`. This test is part of Wave 0.

## Migration and compatibility

No code exists, so no migration is required. Documents proposing rival layouts are archived under `development/archive/` and marked superseded.

## Future evolution and review triggers

Reconsider if TaskControl is split into separately released distributions, or if the web client moves to its own repository.

## Rejected alternatives

Option B was rejected because a top-level `adapters/` directory is not importable from the installed package. Option C was rejected because it erases the port/adapter distinction that ADR 0011 exists to preserve.
