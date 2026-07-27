# TaskControl Implementation Prompt

- Document level: **3 — Specifications**
- Lifecycle state: Canonical
- Supersedes: the three prompts now in `../archive/`

This is the only prompt in the repository. It carries **no scope of its own**. Scope lives in the blueprint, where it changes as waves complete without anyone editing a prompt.

---

You are implementing **TaskControl**, a standalone Python application for defining, scheduling, executing, observing, and governing automated work.

## Before writing code

1. Read `development/00_CONTEXT_INDEX.md`. It is the only entry point. Follow its "For implementation work" reading order.
2. Read `development/10_IMPLEMENTATION_BLUEPRINT.md` and identify the **current wave** from its status table. That wave, and only that wave, is your scope.
3. Read the `development/domain/` files naming the concepts in your wave, and the ADRs your wave lists.
4. Read the `development/ai-operations/` playbook matching your activity.
5. Inspect the existing source, tests, and configuration. Produce a short inventory of what exists, what is missing, and what you will build.

Do not read `development/archive/` — it is superseded and non-authoritative. Do not treat `development/future/` as scope — it is deliberately out of the current phase.

## Authority

When documents disagree, apply the precedence ladder in the context index. If you must apply it, the losing document is defective: fix it in the same change and say so.

A prompt never overrides accepted repository policy. If this prompt appears to conflict with an ADR, the ADR wins.

## Scope discipline

- Build the current wave. Do not implement a later wave's capability. If you need one, define the port, give it the trivial current implementation, and record the rest.
- Do not narrow the wave either. Its acceptance criteria are the deliverable.
- If you find work that belongs to a later wave, add it to `development/future/DEFERRED_CAPABILITIES.md` or the blueprint — not to a `TODO` comment.
- If you find an unresolved decision, add it to `development/OPEN_QUESTIONS.md`. Do not invent a permanent answer.

## Documentation discipline

Discovering a conflict is not a reason to write a new document. Decide which document should be authoritative, migrate unique content into it, update cross-references, and mark the replaced one Superseded, Archived, or Future per ADR 0017. **Do not leave two documents that both claim to be authoritative, and do not create another product-definition document.**

## Implementation constraints

1. Business rules live in `domain/` or `application/`. Never in API routes, CLI commands, ORM models, adapters, or UI components.
2. `domain/` imports only the standard library. `application/` imports no framework, session, or vendor SDK.
3. Timezone-aware datetimes; UTC persistence.
4. Argument arrays, never implicit shell interpolation.
5. Secrets are referenced, never embedded in definitions, logs, examples, generated files, previews, API responses, or tests.
6. Machine-readable error and outcome codes, exactly as ADR 0016 defines them.
7. A declined execution is still a recorded execution.
8. No Phase 1 code writes to a user crontab or any host scheduler configuration.
9. Extension points are preserved even when only one implementation exists.
10. No mock data behind a real interface.

## Quality requirements

- Write tests during the wave, not after it. Cover failure paths, timeouts, retries, cancellation, skips, and recovery.
- Run formatting, linting, type checking, and the full suite. Fix failures rather than reporting them.
- The repository must be runnable and green when you stop.
- Google-style docstrings on public APIs; descriptive names.

## When you finish

Update the blueprint's status table and any Level 0 or Level 1 document your work invalidated. Then report:

1. what you implemented, against the wave's acceptance criteria;
2. changed files grouped by purpose;
3. commands run and their exact results;
4. design decisions made and assumptions taken;
5. known limitations and risks;
6. anything added to `OPEN_QUESTIONS.md` or `DEFERRED_CAPABILITIES.md`;
7. the next wave.

Be precise about what was verified versus what was merely written. Do not describe the result as production-ready unless the evidence supports it.
