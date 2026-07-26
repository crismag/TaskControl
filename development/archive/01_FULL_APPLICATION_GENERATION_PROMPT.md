> **STATUS: SUPERSEDED** — replaced by `development/prompts/IMPLEMENTATION_PROMPT.md`.
>
> Retained for historical reasoning. **Do not use for new implementation.**
>
> Superseded: 2026-07-26. Reason: Instructed an agent to build the entire application including the web UI in one pass, contradicting both the wave roadmap and the Phase 1 scope. Its status list was one of three incompatible outcome vocabularies, resolved by ADR 0016.

---

# Full Application Generation Prompt

Use this prompt with Claude Code, Claude, Codex, or another repository-capable coding agent after giving it access to the entire TaskControl repository.

---

You are the lead architect and principal software engineer for TaskControl.

Your assignment is to attempt a complete, runnable first version of the TaskControl application, not merely scaffold a repository or produce a design proposal.

TaskControl transforms task definitions into reliable, observable, deployable scheduled operations. It is not simply a cron editor. Users define operational intent; TaskControl generates and manages the implementation.

## Mandatory preparation

Before writing code:

1. Read every Markdown file under `development/`.
2. Treat the development context as the authoritative product and engineering specification.
3. Inspect all existing source code, tests, configuration, issues, and repository history available to you.
4. Produce a concise implementation inventory identifying what already exists, what is missing, and what you will build.
5. Identify contradictions or unresolved assumptions. Record material assumptions in documentation rather than silently inventing behaviour.
6. Preserve all accepted architectural decisions.

Do not stop after this analysis. Continue into implementation.

## Primary outcome

Deliver a coherent local-first application that a new contributor can clone and run.

At completion, a user should be able to:

1. Install backend and frontend dependencies.
2. Initialise a SQLite database.
3. Start the TaskControl API and web interface.
4. Use the CLI.
5. Create and edit a task.
6. Configure a command, schedule, runtime profile, run conditions, timeout, retry policy, and expected outcomes.
7. Validate the task.
8. Run the task manually.
9. Preview generated execution and scheduler artefacts.
10. Create and inspect a deployment plan.
11. Apply and remove a safe local cron deployment.
12. View deployment state, execution history, decisions, stdout, stderr, exit status, duration, skip reason, retries, and expectation results.
13. Run the automated test suite successfully.

## Architectural direction

Use a Python modular monolith for the initial server-side implementation.

Preferred baseline:

- Python 3.12 or newer supported version;
- FastAPI;
- Pydantic v2;
- SQLAlchemy 2.x;
- Alembic;
- Typer;
- SQLite by default;
- PostgreSQL compatibility;
- React and TypeScript with Vite for the web UI;
- pytest;
- Ruff;
- mypy or Pyright;
- structured logging.

You may make justified substitutions when the repository already establishes alternatives, but document them.

Keep the domain independent from FastAPI, Typer, SQLAlchemy sessions, and frontend code. API routes, CLI commands, workers, and UI components must call application services rather than reimplement business logic.

## Required domain concepts

Implement coherent representations for:

- Task;
- TaskRevision;
- Schedule;
- ExecutionSpecification;
- RuntimeProfile;
- RunCondition;
- Calendar;
- Target;
- DeploymentPlan;
- Deployment;
- GeneratedArtifact;
- Execution;
- ExecutionAttempt;
- Expectation;
- ExpectationResult;
- NotificationRule or a documented initial placeholder;
- AuditEvent.

Preserve the distinctions between task definition, scheduler artefact, deployment, trigger, execution, attempt, process result, and operational outcome.

## Required statuses

Use explicit and tested statuses. At minimum account for:

- draft;
- valid;
- invalid;
- planned;
- deployed;
- removed;
- pending;
- evaluating;
- skipped;
- blocked;
- running;
- succeeded;
- failed;
- outcome_failed;
- timed_out;
- cancelled;
- lost.

Status names may be adjusted for consistency, but do not collapse skip, block, process failure, outcome failure, timeout, and cancellation into one generic failure.

## Required backend capabilities

### Task management

- CRUD with archive rather than unsafe hard deletion where deployed state exists;
- immutable or traceable task revisions;
- optimistic concurrency or version checking;
- validation with field-level and cross-field errors;
- sample task definitions.

### Scheduling

- structured schedule model;
- time-zone support;
- weekday schedules;
- cron expression support for advanced users;
- next-run preview;
- validation of scheduler capabilities.

### Runtime profiles

- reusable environment variables;
- profile attachment to tasks;
- secret references rather than plaintext secrets;
- deterministic merge order;
- redacted previews.

### Run conditions

Initially implement:

- enabled switch;
- allowed weekdays;
- calendar open/closed check;
- environment or profile value comparison if practical.

Condition evaluations must return structured decisions and reasons.

### Runtime execution

- shell, Python, and direct executable execution;
- argument lists rather than unsafe command concatenation;
- working directory;
- environment resolution;
- stdout and stderr capture;
- timeout;
- cancellation design;
- concurrency lock;
- retry policy;
- manual execution;
- scheduler wrapper execution through the same engine.

### Expected outcomes

Initially support practical checks such as:

- expected exit codes;
- file exists;
- file minimum size;
- file freshness;
- optional text or regular-expression match.

Store each expectation result separately. A process may exit successfully while the overall execution becomes `outcome_failed`.

### Deployment planning

- generate deterministic artefacts;
- preview plan before applying;
- represent additions, changes, removals, and unchanged artefacts;
- preserve task and revision identifiers in generated files;
- calculate content hashes;
- persist plans;
- prevent applying a stale or modified plan without revalidation.

### Local cron adapter

- render managed cron entries or a managed include file safely;
- avoid modifying the user's actual crontab during automated tests;
- support a configurable sandbox deployment root;
- make apply and remove idempotent;
- preserve unmanaged entries;
- expose capability metadata;
- provide clear unsupported-feature validation.

### Persistence and audit

- SQLite setup and migrations;
- PostgreSQL-ready configuration;
- repositories or equivalent clean persistence boundary;
- audit events for mutations, plan creation, apply, removal, and manual execution;
- timestamps stored in UTC;
- UUID identifiers.

### API

Create versioned `/api/v1` endpoints for:

- health and readiness;
- tasks and revisions;
- profiles;
- calendars;
- targets;
- validation;
- deployment plans;
- deployments;
- executions and logs;
- adapter capabilities.

Use OpenAPI metadata, typed schemas, pagination where lists may grow, and structured errors with stable codes and correlation identifiers.

### CLI

Implement useful commands for initialisation, server startup, task management, validation, manual execution, plan generation, plan inspection, deployment apply/remove, execution listing/detail, and adapter discovery.

The CLI may call local application services or the HTTP API, but it must not duplicate domain logic.

## Required web interface

Build a functional operational UI with:

- overview page;
- task list;
- task detail;
- task editor;
- schedule editor;
- runtime profile and condition configuration;
- validation results;
- generated artefact preview;
- deployment plan review;
- deployments list;
- execution history;
- execution detail with logs and decision trail;
- profiles and calendars pages;
- loading, empty, error, and confirmation states.

Prioritise clarity and operational usefulness over elaborate visual effects. Do not create a dashboard full of fake metrics.

## Testing requirements

Build tests during implementation, not after all code is generated.

Required coverage includes:

- domain validation;
- task revision behaviour;
- time-zone and schedule cases;
- condition allow, skip, and block decisions;
- runtime success and process failure;
- timeout;
- retry eligibility and exhaustion;
- expectation pass and fail;
- secret redaction;
- local cron render, plan, apply, idempotent reapply, and remove using a sandbox;
- database migrations;
- API integration tests;
- CLI smoke tests;
- one end-to-end workflow;
- frontend smoke or component tests.

Run formatting, linting, type checking, backend tests, frontend tests, and production builds. Fix failures rather than merely reporting them when possible.

## Security requirements

- Never log plaintext secrets.
- Never expose secret values in generated previews or API responses.
- Avoid `shell=True` by default.
- Validate paths and deployment roots.
- Prevent path traversal.
- Use safe temporary files and atomic replacement for managed artefacts.
- Define an authentication boundary even if local development initially uses a documented single-user mode.
- Do not execute untrusted input in tests.
- Record security-sensitive operations in audit history.

## Developer experience

Provide or update:

- root README with setup and first-use walkthrough;
- `.env.example`;
- `Makefile` or equivalent task runner;
- dependency lock files where appropriate;
- database migration commands;
- development and production start commands;
- Docker Compose for PostgreSQL and optional supporting services;
- sample configuration and tasks;
- architecture overview;
- troubleshooting section;
- contribution guidance.

A clean clone should not require undocumented manual steps.

## Work strategy

Implement in vertical slices and keep the repository runnable after each slice.

Recommended sequence:

1. Repository tooling and quality gates.
2. Domain model and validation.
3. Persistence and migrations.
4. Application services.
5. Runtime engine and local executors.
6. Expectations and execution history.
7. Scheduler artefact generation and local cron deployment.
8. API.
9. CLI.
10. Web UI.
11. Integration and end-to-end tests.
12. Documentation, examples, and polish.

You may adjust this order to fit existing code, but domain and runtime truth must not migrate into the UI.

## Rules against superficial completion

Do not:

- stop after creating folders and placeholder classes;
- generate routes that always return mock data;
- create a UI disconnected from the backend;
- claim deployment support when only text rendering exists;
- call a process successful without evaluating configured outcomes;
- silently drop unsupported configuration;
- put plaintext secrets in example files;
- remove abstractions only because the local version has one implementation;
- create premature microservices;
- leave the repository with failing tests without clearly documenting unavoidable blockers.

## Handling limits

Attempt as much of the complete application as the environment allows.

If tool, context, or execution limits prevent completion:

1. Keep all completed code runnable and tested.
2. Do not leave half-applied migrations or broken imports.
3. Create `development/IMPLEMENTATION_STATUS.md` containing:
   - completed capabilities;
   - exact commands and test results;
   - incomplete capabilities;
   - known defects;
   - assumptions;
   - the next ordered tasks with file-level guidance.
4. Continue until a genuine environmental limit blocks further work.

Do not stop merely to ask permission between routine implementation phases.

## Final report

When finished, provide:

- concise architecture summary;
- implemented user journeys;
- significant files and modules;
- database and API summary;
- test and build commands with results;
- security controls implemented;
- assumptions and limitations;
- remaining roadmap.

Be precise and honest. Do not describe the application as production-ready unless the evidence supports that claim.

Begin by reading the repository and all files under `development/`, then implement the application.

---

## Suggested invocation

Use a repository-capable agent and provide this instruction:

> Read and follow `development/prompts/01_FULL_APPLICATION_GENERATION_PROMPT.md`. Load every file under `development/` as authoritative context. Attempt the complete runnable TaskControl application, continue through implementation and tests without stopping after scaffolding, and leave a precise `development/IMPLEMENTATION_STATUS.md` if any part remains incomplete.
