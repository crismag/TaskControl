# ADR 0019: Composition Roots Live Inside the Installed Package

- Document level: **1 — Architecture**
- Lifecycle state: Canonical
- Status: Accepted
- Date: 2026-07-26
- Owners: TaskControl maintainers
- Supersedes: the top-level `apps/` placement in ADR 0015 (that ADR otherwise stands)
- Superseded by: None
- Related documents: ADR 0015, `development/engineering/repository/10_REPOSITORY_STRUCTURE.md`, `development/10_IMPLEMENTATION_BLUEPRINT.md`

## Context

ADR 0015 placed composition roots in a top-level `apps/` directory, outside `src/taskcontrol/`. Implementing Wave 0 showed that this cannot work.

A `src/` layout installs exactly the packages named in `[tool.hatch.build.targets.wheel]`. Anything outside `src/taskcontrol/` is absent from the wheel. Two Wave 0 requirements depend on composition roots being importable from an installed distribution:

1. The `taskctl` console script is an entry point of the form `module:attribute`. The module must be importable after `pip install taskcontrol`.
2. The API is started by an ASGI server from an import string such as `uvicorn taskcontrol.apps.api.main:create_app --factory`. The factory must be importable in the deployed environment.

With composition roots at top-level `apps/`, both fail outside a source checkout. Adding `apps` as a second distribution package would claim the generic top-level name `apps` in every environment that installs TaskControl, which is unacceptable for a library-shaped distribution.

This is the same objection ADR 0015 used to reject its Option B — that a top-level `adapters/` directory "is not importable from the installed package". The objection applies with equal force to `apps/`, and ADR 0015 did not notice. The defect was invisible while the repository contained no code.

## Decision drivers

- Console scripts and ASGI factories must resolve from an installed wheel, not only a source tree.
- The distribution must not claim generic top-level import names.
- The separation ADR 0015 wanted — composition distinct from transport — is valuable and must survive.
- The fix should be the smallest one that preserves ADR 0015's intent.

## Considered options

### Option A — Ship `apps/` as a second top-level package

Keeps the tree as written. Claims the import name `apps` globally; collides with any other distribution doing the same. Rejected.

### Option B — Move composition roots to `src/taskcontrol/apps/`

Entry points become `taskcontrol.apps.cli.main:app` and `taskcontrol.apps.api.main:create_app`. The composition-versus-transport separation is preserved exactly; only the location changes.

### Option C — Abolish composition roots; wire inside `api/` and `cli/`

Fewer directories, but merges process wiring with transport code, which is the coupling ADR 0015 set out to prevent.

## Decision

Adopt **Option B**. Composition roots live at `src/taskcontrol/apps/{api,cli,worker}/`. There is no top-level `apps/` directory.

Responsibilities are unchanged from ADR 0015: `apps/` builds settings, configures logging, instantiates adapters, mounts routers or commands, and starts a process. It contains no business rules and no branching on business conditions. `taskcontrol/api/` and `taskcontrol/cli/` continue to own transport.

Entry points:

```toml
[project.scripts]
taskctl = "taskcontrol.apps.cli.main:main"
```

```bash
uvicorn taskcontrol.apps.api.main:create_app --factory
```

## Rationale

Option B changes one path segment and preserves every property ADR 0015 argued for. Options A and C each sacrifice something ADR 0015 explicitly protected.

## Consequences

### Positive

- `taskctl` works from an installed wheel, not only an editable source checkout.
- The ASGI factory resolves in containers and production deployments.
- One less top-level directory; the whole runtime is one importable tree.

### Negative or accepted trade-offs

- `taskcontrol.apps.api` and `taskcontrol.api` are adjacent names that must be explained. `10_REPOSITORY_STRUCTURE.md` states the distinction: `apps/` wires, `api/` and `cli/` transport.

### Risks and mitigations

- Risk: contributors put routers in `apps/` because the names are similar — mitigation: the architecture test asserts `apps/` modules import from `api`/`cli`/`infrastructure` and never define routes or commands themselves.

## Implementation constraints

- No module under `src/taskcontrol/apps/` defines a route, a CLI command body, or a domain rule.
- `apps/` may import any layer; nothing imports `apps/` except entry points and tests.

## Validation

`pip install .` into a clean environment, then run `taskctl version` and import the ASGI factory from outside the source tree. Both must succeed. The architecture test enforces the import constraints.

## Migration and compatibility

Applied during Wave 0, before any code existed at the old location. ADR 0015's layout table is corrected by this ADR; `10_REPOSITORY_STRUCTURE.md` is updated to match and remains the single normative statement of the tree.

## Future evolution and review triggers

Reconsider if TaskControl is split into multiple distributions, where a separate `taskcontrol-worker` package might legitimately own its own composition root.

## Rejected alternatives

Option A claims a generic top-level import name. Option C reintroduces the composition/transport coupling ADR 0015 exists to prevent.
