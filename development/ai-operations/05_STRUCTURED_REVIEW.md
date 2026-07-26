# Structured Review Playbook

## Objective

Review AI-generated work from multiple engineering perspectives before requesting human approval.

## Review sequence

### Requirement review

- Does the change satisfy the stated outcome and acceptance criteria?
- Were assumptions or non-goals silently expanded?
- Are user-visible and operational behaviours documented?

### Domain review

- Are domain terms and ownership correct?
- Are invariants enforced in the domain or application layer?
- Are state transitions explicit?
- Does the change preserve immutable revision semantics and other accepted domain rules?

### Architecture review

- Do dependencies point inward?
- Are frameworks and external systems behind adapters?
- Is business logic leaking into delivery or persistence code?
- Does the change follow accepted ADRs?
- Has unnecessary distribution or abstraction been introduced?

### Data review

- Are constraints, transactions, indexes, migrations, and concurrency controls correct?
- Can partial failure corrupt or ambiguously update state?
- Are compatibility and rollback implications understood?

### Contract review

- Are API, CLI, event, plugin, and UI contracts explicit and compatible?
- Are errors stable, actionable, and free of sensitive data?

### Quality review

- Do tests cover success, rejection, and material failure paths?
- Is the code readable, typed, deterministic, and maintainable?
- Is unrelated churn excluded?

### Documentation review

- Are architecture, domain, ADR, operations, and usage documents still accurate?
- Are assumptions and deferred work traceable?

## Review output

Classify findings as:

- **Blocker** — correctness, data loss, security, invariant, or architectural violation.
- **Major** — substantial maintainability, reliability, compatibility, or operational issue.
- **Minor** — local improvement that does not invalidate the change.
- **Question** — unresolved intent or evidence needed.

The self-review must name concrete files, behaviours, or scenarios. Generic statements such as "looks good" are not evidence.

## Approval readiness

A change is ready for human review when blockers and majors are resolved or explicitly accepted by an authorised reviewer, test evidence is recorded, and remaining risks are visible in the PR.