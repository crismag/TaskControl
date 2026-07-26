> **STATUS: SUPERSEDED** — replaced by ADR 0015, `development/engineering/repository/10_REPOSITORY_STRUCTURE.md`, and `development/architecture/ARCHITECTURE_OVERVIEW.md`.
>
> Retained for historical reasoning. **Do not use for new implementation.**
>
> Superseded: 2026-07-26. Reason: Proposed one of four competing repository layouts, resolved by ADR 0015. Stack list merged into the architecture overview; CLI command set into the implementation blueprint.

---

# Technology and Repository Structure

## Initial stack

- Python 3.12+
- FastAPI
- Pydantic v2
- SQLAlchemy 2
- Alembic
- SQLite for personal mode
- PostgreSQL for server mode
- Typer for CLI
- Pytest
- Ruff and mypy
- TypeScript web client added after the API/domain foundation

## Recommended repository structure

```text
TaskControl/
├── README.md
├── pyproject.toml
├── src/taskcontrol/
│   ├── api/
│   ├── cli/
│   ├── application/
│   ├── domain/
│   │   ├── tasks/
│   │   ├── schedules/
│   │   ├── calendars/
│   │   ├── profiles/
│   │   ├── conditions/
│   │   ├── deployments/
│   │   ├── executions/
│   │   └── monitoring/
│   ├── runtime/
│   ├── adapters/
│   │   ├── schedulers/
│   │   ├── executors/
│   │   ├── persistence/
│   │   ├── deployment/
│   │   ├── monitoring/
│   │   ├── notifications/
│   │   └── secrets/
│   ├── schemas/
│   └── common/
├── web/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   └── fixtures/
├── examples/
├── docs/
├── development/
│   ├── prompts/
│   └── decisions/
├── scripts/
└── .github/workflows/
```

## Structural rules

- Domain modules must not import FastAPI, SQLAlchemy ORM models, Typer, or platform-specific adapters.
- Application services coordinate domain objects and ports.
- Adapters implement ports and contain external-system details.
- API and CLI translate requests into application commands; they do not implement business rules.
- Runtime execution is reusable from CLI, API, scheduler, and tests.
- Generated artefacts live outside source packages and are never silently treated as authoritative definitions.

## Packaging

Expose console commands:
- `taskctl`
- optionally `taskcontrold` later

Initial commands should include:
- `taskctl init`
- `taskctl validate`
- `taskctl task create|list|show`
- `taskctl schedule preview`
- `taskctl run`
- `taskctl deploy plan|apply`
- `taskctl executions list|show`

## Data and schema approach

Use Pydantic DTOs at boundaries and explicit domain types internally. Persist immutable definition versions plus mutable lifecycle metadata. Add JSON Schema export for portable task bundles.

## Future native agent

Reserve `agent_protocol_version`, deployment-bundle format, heartbeats, capability reports, and signed result envelopes in design documents only. Do not create a C++, Go, or Rust agent until local and SSH-based semantics are stable.
