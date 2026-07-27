# TaskControl Architecture Decision Records

- Document level: **1 — Architecture**
- Lifecycle state: Canonical

This directory contains the authoritative Architecture Decision Records (ADRs) for TaskControl.

ADRs preserve the context, alternatives, rationale, consequences, and future review conditions behind significant technical choices. They complement the vision, architecture, domain, and engineering handbooks.

## Authority

Accepted ADRs are binding unless superseded by a later accepted ADR. Implementation code, prompts, reviews, and documentation must remain consistent with accepted decisions.

The repository-wide precedence ladder is published once, in `../00_CONTEXT_INDEX.md` (ADR 0017). ADRs sit directly below Level 0 product constraints on it.

An ADR may refine a lower-level document but must not silently contradict approved product intent.

## Status values

- Proposed — under review and not yet binding
- Accepted — approved and binding
- Deprecated — retained for history but no longer recommended
- Superseded — replaced by another ADR
- Rejected — considered but not adopted

## ADR lifecycle

1. Identify a decision with long-term architectural impact.
2. Record context, constraints, alternatives, and decision drivers.
3. Evaluate operational, security, migration, and maintenance consequences.
4. Review against existing ADRs and engineering laws.
5. Mark accepted only when the repository owner approves the decision.
6. Supersede rather than rewrite historical reasoning.

## Current ADRs

- [0000 — ADR Template](0000_ADR_TEMPLATE.md)
- [0001 — Python as the Primary Application Language](0001_PYTHON_PRIMARY_LANGUAGE.md)
- [0002 — Modular Monolith as the Initial Architecture](0002_MODULAR_MONOLITH.md)
- [0003 — Domain-First Layered Architecture](0003_DOMAIN_FIRST_LAYERING.md)
- [0004 — FastAPI and Typer as Delivery Adapters](0004_FASTAPI_TYPER_ADAPTERS.md)
- [0005 — SQLAlchemy and Alembic for Persistence](0005_SQLALCHEMY_ALEMBIC.md)
- [0006 — Immutable Task Revisions](0006_IMMUTABLE_TASK_REVISIONS.md)
- [0007 — Scheduler Abstraction and Candidate Triggers](0007_SCHEDULER_ABSTRACTION.md)
- [0008 — Execution, Attempts, and Outcome Separation](0008_EXECUTION_ATTEMPT_OUTCOME.md)
- [0009 — Deterministic Layered Configuration](0009_LAYERED_CONFIGURATION.md)
- [0010 — Plan-Apply-Verify Deployment Model](0010_DEPLOYMENT_PLAN_APPLY_VERIFY.md)
- [0011 — Ports and Adapters for External Integrations](0011_PORTS_AND_ADAPTERS.md)
- [0012 — SQLite First with PostgreSQL Compatibility](0012_SQLITE_POSTGRESQL_COMPATIBILITY.md)
- [0013 — React and TypeScript for the Web Interface](0013_REACT_TYPESCRIPT_FRONTEND.md)
- [0014 — Future Remote Agents Without Premature Distribution](0014_FUTURE_REMOTE_AGENTS.md)
- [0015 — Canonical Repository Layout](0015_CANONICAL_REPOSITORY_LAYOUT.md)
- [0016 — Execution State and Outcome Taxonomy](0016_EXECUTION_STATE_AND_OUTCOME_TAXONOMY.md)
- [0017 — Documentation Levels and Repository Canonicalization](0017_DOCUMENTATION_LEVELS_AND_CANONICALIZATION.md)
- [0018 — Internal Scheduler Before Scheduler-Artefact Deployment](0018_INTERNAL_SCHEDULER_BEFORE_ARTEFACT_DEPLOYMENT.md)
- [0019 — Composition Roots Live Inside the Installed Package](0019_COMPOSITION_ROOTS_INSIDE_THE_PACKAGE.md)
- [0020 — Reason Codes Distinguish Termination Causes](0020_TERMINATION_CAUSE_REASON_CODES.md)
- [0021 — Overlap Locking Is Process-Local Until Wave 5](0021_PROCESS_LOCAL_OVERLAP_LOCKING.md)

## When an ADR is required

Create an ADR when a change:

- introduces or replaces a core framework or data store;
- changes dependency direction or module boundaries;
- alters persistence, revision, scheduling, execution, deployment, or security semantics;
- introduces distributed coordination;
- creates a public compatibility commitment;
- removes an intentional extension point;
- adds a dependency with broad architectural influence;
- accepts significant operational or security trade-offs.

Minor implementation details do not require ADRs unless they establish a lasting precedent.
