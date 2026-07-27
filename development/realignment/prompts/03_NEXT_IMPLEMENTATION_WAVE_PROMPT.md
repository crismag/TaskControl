# Prompt — First Implementation Wave After Realignment

Use this only after the canonical product-realignment PR is merged and the revised blueprint confirms this wave.

## Assignment

Implement the smallest complete cron-backed managed-task vertical slice while preserving Waves 0–3.

## User outcome

A user can define a recurring task without editing crontab, preview the generated change, apply it safely, allow cron to activate it, and inspect its recorded outcome.

## Required capability

1. Define one local scheduled task using the existing task model.
2. Accept a human-friendly schedule and an advanced cron expression where already supported.
3. Render a deterministic managed cron artefact through a cron adapter.
4. Provide plan, apply, verify, and status operations.
5. Preserve unrelated and unmanaged cron entries.
6. Invoke the existing Wave 3 execution service through a stable short-lived command or generated wrapper.
7. Persist execution and attempt results through the existing repositories.
8. Confirm that the API/web process is not required to stay alive for cron activation.
9. Expose the intended and installed schedule through CLI or API.

## Suggested user flow

```text
create task
  -> validate definition
  -> cron plan
  -> cron apply
  -> cron read-back verification
  -> wait for or safely simulate cron activation
  -> inspect execution outcome
```

The exact command names must follow the canonical CLI/API design after realignment. Do not expose `taskctl execute <task>` as the primary scheduled-job workflow, although an internal or administrative run-now command may exist.

## Safety requirements

- Never rewrite an entire crontab without preserving unmanaged content.
- Generate stable managed identifiers.
- Escape commands and arguments safely.
- Validate execution user, paths, permissions, working directory, and schedule.
- Provide dry-run/plan output before mutation.
- Verify the installed artefact by reading it back.
- Fail closed on ambiguous managed-block identity.
- Provide a reversible rollback path for failed apply.
- Do not permit arbitrary remote shell commands through the ordinary task-submission API.

## Architecture requirements

- Domain and application layers depend on scheduler-management ports, not cron libraries.
- Cron rendering and installation live in adapters.
- The execution service remains bounded and short-lived.
- No internal recurring scheduler loop.
- No hidden in-memory timer or polling loop.
- No queue implementation in this wave unless the revised blueprint explicitly combines it.

## Tests

Include at least:

- human-friendly schedule to expected cron rendering;
- advanced expression validation;
- deterministic rendering;
- unmanaged-entry preservation;
- first apply;
- idempotent re-apply;
- schedule update plan and apply;
- disable and enable;
- read-back verification;
- malformed managed block rejection;
- missing runnable rejection;
- execution launched by the installed/generated cron boundary;
- attempt and outcome persistence;
- API/UI process absent during local activation.

Use temporary crontab files or a test adapter for most tests. Add a controlled integration test against a real crontab only when safe and isolated.

## Documentation

Update the blueprint outcome, relevant specifications, examples, CLI/API documentation, and operational runbook in the same PR.

## Completion rule

The wave is complete only when the repository demonstrates the full value chain rather than merely rendering a cron string.
