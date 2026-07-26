> **STATUS: SUPERSEDED** — replaced by `development/engineering/` (the engineering handbook).
>
> Retained for historical reasoning. **Do not use for new implementation.**
>
> Superseded: 2026-07-26. Reason: Fully absorbed. Golden-file, contract, and property-test requirements unique to this document were merged into `development/engineering/quality/30_TESTING_AND_QUALITY_STRATEGY.md`.

---

# Engineering Standards

## General

- Prefer clear, explicit code over clever abstractions.
- Use descriptive names; avoid single-letter variables outside tiny mathematical scopes.
- Keep functions focused and side effects visible.
- Add Google-style docstrings to public Python APIs.
- Use type hints throughout production code.
- Treat warnings, lint failures, type errors, and test failures as build failures.

## Python

- Target Python 3.12 or newer.
- Use `pathlib`, timezone-aware datetimes, enums, dataclasses or Pydantic models where appropriate.
- Avoid shell execution unless explicitly requested by the task definition.
- Use `subprocess` argument arrays by default.
- Normalize exceptions into domain-specific error types at adapter boundaries.
- Keep domain logic independent of frameworks and persistence.

## Logging

- Use structured logging with execution, task, deployment, and correlation identifiers.
- Support console and file handlers.
- Never log secret values.
- Record condition decisions and outcome reasons.
- Preserve stdout and stderr separately while allowing a combined human-readable view.

## Testing

- Unit tests for domain rules and parsers.
- Integration tests for persistence, runtime, scheduler rendering, and subprocess behaviour.
- Contract tests shared by adapters.
- Golden-file tests for deterministic generated artefacts.
- Property or parameterized tests for schedules, calendars, and configuration precedence.
- Tests must cover failure paths, timeouts, retries, cancellation, skips, and rollback.

## Security

- Validate all external input.
- Default to least privilege.
- Separate secret references from resolved secret values.
- Protect against command injection, path traversal, unsafe file permissions, and symlink attacks.
- Do not overwrite unmanaged crontab content.
- Document trust boundaries and threat assumptions for every remote capability.

## Database and migrations

- All schema changes use Alembic migrations.
- Store timestamps in UTC.
- Preserve immutable historical meaning through version references and configuration hashes.
- Avoid database-specific domain behaviour where SQLite and PostgreSQL differ.

## API

- Version public APIs.
- Return machine-readable error codes with human explanations.
- Support idempotency for deployment and execution-trigger endpoints where applicable.
- Never expose internal stack traces in normal responses.

## Documentation and completion

Every implementation wave must update:
- user-facing documentation;
- relevant development context;
- example configurations;
- migration or compatibility notes;
- test coverage.

AI coding agents must finish with a concise report listing changed files, commands run, test results, unresolved risks, and recommended next wave.
