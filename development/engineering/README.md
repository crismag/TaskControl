# TaskControl Engineering Governance

This directory is the authoritative handbook for how TaskControl is engineered by humans and AI coding agents.

It complements the product, architecture, and domain packages:

- `development/vision/` explains why TaskControl exists.
- `development/architecture/` explains the intended system shape.
- `development/domain/` defines the product language, rules, and lifecycles.
- `development/engineering/` defines how implementation work must be performed.

## Authority

When implementation convenience conflicts with this handbook, the handbook wins unless an explicit architecture decision record approves an exception.

## Reading order

1. `00_ENGINEERING_CHARTER.md`
2. `philosophy/01_ENGINEERING_LAWS.md`
3. `repository/10_REPOSITORY_STRUCTURE.md`
4. `repository/11_DEPENDENCY_RULES.md`
5. `standards/20_PYTHON_AND_APPLICATION_STANDARDS.md`
6. `standards/21_API_AND_DATABASE_STANDARDS.md`
7. `standards/22_RUNTIME_OBSERVABILITY_AND_SECURITY.md`
8. `quality/30_TESTING_AND_QUALITY_STRATEGY.md`
9. `governance/40_DEFINITION_OF_DONE.md`
10. `governance/41_REPOSITORY_REVIEW_PROCESS.md`
11. `ai/90_AI_ENGINEERING_PLAYBOOK.md`
12. `ai/91_AI_CHANGE_POLICY.md`

## Non-negotiable themes

- Business rules remain framework-independent.
- Dependencies point inward toward the domain.
- Configuration and generated artefacts are deterministic and explainable.
- Security, auditing, observability, tests, and documentation are implementation requirements.
- AI-generated changes receive the same scrutiny as human-generated changes.
- Assumptions, shortcuts, exceptions, and deferred work must be visible.

## Change control

Changes to this handbook should be reviewed as engineering policy changes. A change must explain:

- the problem being solved;
- the affected engineering behaviour;
- compatibility implications;
- migration or adoption steps;
- whether an ADR is required.
