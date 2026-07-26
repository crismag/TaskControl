# Full Application Acceptance Checklist

Use this checklist to review a full-application generation attempt. A checked item should be supported by working code, tests, or documentation—not only a placeholder.

## Repository and setup

- [ ] Root README explains the product and local quick start.
- [ ] Python environment installs reproducibly.
- [ ] Frontend dependencies install reproducibly.
- [ ] `.env.example` contains no secrets.
- [ ] SQLite works without external infrastructure.
- [ ] PostgreSQL configuration is available.
- [ ] Database migrations run from a clean database.
- [ ] API, CLI, worker, and web start commands are documented.
- [ ] Formatting, linting, type checking, tests, and builds have commands.

## Architecture

- [ ] Domain logic is independent of FastAPI, Typer, and React.
- [ ] API and CLI use application services.
- [ ] Persistence is behind a clear boundary.
- [ ] Adapter interfaces expose capabilities.
- [ ] No premature microservice requirement exists.
- [ ] Task, revision, deployment, execution, and outcome remain distinct.

## Task definition

- [ ] Task CRUD works.
- [ ] Task archive behaviour is safe.
- [ ] Revisions or equivalent traceability exist.
- [ ] Validation reports structured errors.
- [ ] Concurrency/version conflicts are handled.
- [ ] Sample task definitions exist.

## Scheduling

- [ ] Structured weekday/time schedules work.
- [ ] Time zones are explicit.
- [ ] Advanced cron expressions are supported or clearly deferred.
- [ ] Next-run preview exists.
- [ ] Unsupported scheduler semantics fail validation.

## Profiles, conditions, and calendars

- [ ] Runtime profiles are reusable.
- [ ] Secret references are separate from values.
- [ ] Secret values are redacted.
- [ ] Enabled switch condition works.
- [ ] Weekday condition works.
- [ ] Calendar open/closed condition works.
- [ ] Every condition returns an explainable decision.

## Runtime

- [ ] Shell execution works safely.
- [ ] Python execution works.
- [ ] Direct executable execution works.
- [ ] Working directory and environment are supported.
- [ ] stdout and stderr are captured.
- [ ] Timeout is enforced.
- [ ] Retry policy is implemented and tested.
- [ ] Concurrency policy or lock exists.
- [ ] Manual execution uses the production runtime path.
- [ ] Skip, block, failure, timeout, cancellation, and success are distinguishable.

## Expected outcomes

- [ ] Expected exit codes work.
- [ ] File existence check works.
- [ ] File size check works.
- [ ] File freshness check works.
- [ ] Each expectation result is stored.
- [ ] Process success with outcome failure is represented correctly.

## Deployment

- [ ] Generated artefacts are deterministic.
- [ ] Content hashes are stored.
- [ ] Deployment plans show additions, changes, removals, and unchanged items.
- [ ] Plans are previewable before side effects.
- [ ] Stale plans cannot be applied silently.
- [ ] Local cron rendering works.
- [ ] Tests use a sandbox rather than the real crontab.
- [ ] Apply is idempotent.
- [ ] Remove is idempotent.
- [ ] Unmanaged scheduler content is preserved.
- [ ] Deployment state and audit events are stored.

## API

- [ ] `/api/v1` is used.
- [ ] Health and readiness endpoints work.
- [ ] Task endpoints work.
- [ ] Profile and calendar endpoints work.
- [ ] Validation endpoint works.
- [ ] Plan and deployment endpoints work.
- [ ] Execution endpoints and logs work.
- [ ] Adapter capability endpoint works.
- [ ] Errors have stable codes and correlation IDs.
- [ ] OpenAPI output is usable.

## CLI

- [ ] Initialisation command works.
- [ ] Task create/list/show/update commands work.
- [ ] Validation command works.
- [ ] Manual run command works.
- [ ] Plan create/show commands work.
- [ ] Deployment apply/remove commands work.
- [ ] Execution list/show commands work.
- [ ] Adapter discovery works.
- [ ] CLI does not duplicate domain logic.

## Web UI

- [ ] Overview page uses real API data.
- [ ] Task list and task detail work.
- [ ] Task editor covers initial configuration.
- [ ] Validation feedback is visible.
- [ ] Artefact and plan previews are readable.
- [ ] Deployments are visible.
- [ ] Execution history is visible.
- [ ] Execution detail includes logs and decisions.
- [ ] Loading, empty, error, and confirmation states exist.
- [ ] UI does not depend on mock data in normal operation.

## Security

- [ ] Plaintext secrets are not persisted in task definitions.
- [ ] Secrets are absent from logs and previews.
- [ ] `shell=True` is not the default execution path.
- [ ] Path traversal protections exist.
- [ ] Managed artefact writes are atomic where practical.
- [ ] Deployment roots are constrained.
- [ ] Authentication boundary is documented and implemented at the intended initial level.
- [ ] Security-sensitive actions generate audit events.

## Tests and quality

- [ ] Domain tests pass.
- [ ] Schedule/time-zone tests pass.
- [ ] Condition tests pass.
- [ ] Runtime result tests pass.
- [ ] Timeout and retry tests pass.
- [ ] Expectation tests pass.
- [ ] Secret-redaction tests pass.
- [ ] Cron adapter contract tests pass.
- [ ] Migration tests pass.
- [ ] API integration tests pass.
- [ ] CLI smoke tests pass.
- [ ] Frontend tests pass.
- [ ] At least one complete end-to-end workflow passes.
- [ ] Backend formatting and linting pass.
- [ ] Type checking passes or exclusions are documented.
- [ ] Frontend production build passes.

## Documentation and honesty

- [ ] Implemented scope is documented.
- [ ] Assumptions are documented.
- [ ] Known limitations are documented.
- [ ] No unsupported production-readiness claim is made.
- [ ] `development/IMPLEMENTATION_STATUS.md` exists when work remains.
- [ ] Continuation tasks are ordered and specific.

## Final acceptance

The first full application is accepted when a clean local environment can create, validate, manually run, plan, deploy, observe, and remove a scheduled task through a coherent combination of API, CLI, and web UI, with automated tests demonstrating the essential operational states.