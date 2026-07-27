> **STATUS: SUPERSEDED** — replaced by `development/prompts/IMPLEMENTATION_PROMPT.md`.
>
> Retained for historical reasoning. **Do not use for new implementation.**
>
> Superseded: 2026-07-26. Reason: One of three prompts giving contradictory build scope. Scope now lives in the blueprint, not in prompts (ADR 0017).

---

# Master Implementation Prompt

Use this prompt with Codex, Claude, or another repository-capable coding agent.

---

You are implementing **TaskControl**, a Python-first scheduled-task operations platform.

Before changing code, read all files under `development/` in numeric order. Treat them as authoritative unless repository code or a newer architecture decision record explicitly supersedes them.

## Mission

Build the most complete coherent implementation possible for the current delivery wave while preserving the architecture required for later personal, multi-user, multi-host, enterprise, and federated operation.

TaskControl must transform declarative task definitions into reliable, observable, production-ready scheduled operations. It must separate:

- task definition;
- trigger;
- run conditions;
- execution profile;
- deployment;
- execution attempt;
- outcome;
- monitoring expectation.

## Initial technical direction

Use:
- Python 3.12+;
- FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, Typer, Pytest, Ruff, and mypy;
- SQLite initially with PostgreSQL compatibility;
- a `src/` package layout;
- ports-and-adapters boundaries;
- framework-independent domain logic;
- TypeScript only when implementing the web wave.

Do not implement C++. Do not create a native agent yet. Keep schemas, bundle formats, and future agent interfaces language-neutral.

## Required first execution

If the repository contains only documentation, implement **Wave 0** from `development/05_DELIVERY_ROADMAP.md` and then continue into **Wave 1** only if Wave 0 is complete, tested, and the remaining changes stay coherent.

Wave 0 must include at minimum:
- `pyproject.toml`;
- importable `src/taskcontrol` package;
- version and health information;
- Typer CLI entry point;
- minimal FastAPI application factory;
- test, lint, formatting, and typing configuration;
- GitHub Actions CI;
- `.gitignore`;
- developer setup documentation;
- initial ADR template and architecture decision recording the Python-first modular-monolith choice.

Wave 1 should include typed definitions for task, executor, trigger, runtime controls, profile references, run conditions, deployment, execution attempt, outcome, and monitoring expectation. Add YAML/JSON loading, semantic validation, examples, JSON Schema generation, and thorough unit tests.

## Implementation constraints

1. Do not place business rules in API routes, CLI commands, ORM models, or adapter implementations.
2. Domain code must not import FastAPI, Typer, or SQLAlchemy.
3. Use timezone-aware datetimes and persist UTC semantics.
4. Do not execute untrusted strings through a shell by default.
5. Never embed secret values in definitions, logs, examples, generated files, or tests.
6. Use explicit machine-readable error and outcome codes.
7. Record skipped execution as a legitimate execution attempt in later runtime work.
8. Keep generated scheduler artefacts reproducible and non-authoritative.
9. Preserve unmanaged cron content when cron deployment is implemented.
10. Avoid speculative distributed infrastructure and empty enterprise scaffolding.

## Quality requirements

- Add or update tests with every behaviour change.
- Include negative and edge-case tests.
- Run formatting, linting, typing, and tests.
- Keep public APIs documented.
- Use descriptive names and Google-style docstrings.
- Prefer complete vertical slices over placeholders.
- Mark intentionally deferred work in a precise backlog section, not scattered TODO comments.

## Repository hygiene

- Do not commit generated caches, virtual environments, databases, logs, or secrets.
- Keep examples runnable and safe.
- Update README and development documents when implementation changes an assumption.
- Add an ADR for material architectural changes.
- Do not rewrite unrelated files.

## Completion report

At the end, provide:
1. summary of implemented capabilities;
2. changed-file list grouped by purpose;
3. commands executed;
4. exact test/lint/type-check results;
5. design decisions made;
6. known limitations and risks;
7. recommended next implementation wave;
8. any questions that truly block future work, without using unanswered questions as a reason to leave the current wave incomplete.

Proceed autonomously. Make reasonable, documented assumptions. Prioritize a working, tested foundation over superficial breadth.

---

## Suggested use

For a broad initial generation, provide this file plus the full `development/` directory to the coding agent and instruct it to implement through Wave 1. For later work, create a wave-specific prompt that references this master prompt and narrows the requested acceptance criteria.
