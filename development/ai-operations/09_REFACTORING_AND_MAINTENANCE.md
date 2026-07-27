# Refactoring and Maintenance Playbook

- Document level: **3 — Specifications**
- Lifecycle state: Canonical

## Objective

Improve structure, clarity, reliability, or performance without disguising behavioural changes or weakening architectural controls.

## Refactoring rules

- Establish the current behaviour with tests before restructuring it.
- Keep refactors separate from feature work unless the smallest safe implementation requires both.
- Preserve public contracts, domain invariants, persistence semantics, and audit behaviour unless an explicit change is approved.
- Prefer small reversible steps.
- Remove obsolete paths only after confirming no supported caller depends on them.
- Do not introduce abstractions without at least one clear current responsibility.
- Treat dependency upgrades as engineering changes requiring compatibility and security review.

## Maintenance categories

### Corrective

Fix a demonstrated defect. Preserve a reproducing test and repair the owning layer.

### Adaptive

Respond to platform, dependency, database, operating system, or external API changes. Record compatibility boundaries.

### Perfective

Improve maintainability, performance, observability, usability, or developer experience without inventing product requirements.

### Preventive

Reduce credible future risk, such as unsupported dependencies, fragile migrations, missing recovery tests, or repeated architectural violations.

## Performance work

Measure before optimising. Record the workload, baseline, bottleneck evidence, proposed target, and trade-offs. Do not sacrifice correctness, explainability, or auditability for unmeasured speed.

## Dependency updates

Review release notes, licence, maintenance status, security advisories, Python/Node/database compatibility, transitive impact, lockfile changes, and rollback. Avoid broad unattended upgrades in a feature PR.

## Completion evidence

Show that behaviour remains correct, relevant tests pass, complexity or risk is materially reduced, and documentation or ADRs remain accurate.
