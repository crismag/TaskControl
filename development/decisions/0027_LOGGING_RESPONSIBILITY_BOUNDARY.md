# ADR 0027: TaskControl Logs Dispatch; The Runnable Logs Its Own Work

- Document level: **1 — Architecture**
- Lifecycle state: Canonical
- Status: Accepted
- Date: 2026-07-27
- Owners: TaskControl maintainers
- Supersedes: None
- Superseded by: None
- Related documents: ADR 0016, ADR 0024, ADR 0025, `development/OPEN_QUESTIONS.md` Q7, `development/reviews/R1_WAVE3_COMPATIBILITY.md`

## Context

ADR 0024 requires a local journal when a task runs with control state unreachable. Q7 asked
what format it takes, where it lives, and — the hard part — what happens when the journal
write itself fails *after* the runnable has already produced side effects.

Answering that surfaced a prior question nobody had settled: **how much is TaskControl
supposed to log at all?**

Wave 3 captures a task's entire stdout and stderr into the database. That quietly makes
TaskControl the log of record for every managed job — which means its storage grows with the
verbosity of work it does not control, its journal must carry arbitrary application output,
and a chatty job becomes a TaskControl capacity problem.

That is not the division of labour production engineering actually uses. A well-written
operational script already logs its own detail, to its own file, with its own rotation and
retention. What was always missing is the layer above: what was dispatched, when, whether it
ran, and what it returned.

## Decision drivers

- TaskControl is a dispatch and monitoring platform, not a log aggregator.
- A task's detailed logging belongs to the task, where its author controls format and
  retention.
- The journal must stay small enough to write reliably when things are already going wrong.
- Diagnostic evidence still has to exist — an operator investigating a 3am failure needs
  something.

## Considered options

### Option A — TaskControl is the log of record

Capture everything, store it, serve it. Convenient in a demo. Makes storage a function of
other people's verbosity, forces the journal to carry arbitrary output at the worst moment,
and duplicates logging the task already does.

### Option B — TaskControl logs dispatch and outcome; the runnable logs its work

A clear boundary. Captured output becomes bounded diagnostic evidence rather than the
authoritative log. Requires saying plainly that TaskControl is not where you go to read a
report's contents.

## Decision

Adopt **Option B**.

### The boundary

| Owner | Logs |
|---|---|
| **TaskControl** | That a capability was activated, by which mechanism, under which revision; that a claim was or was not acquired; that a process started, and how it ended — exit status, signal, termination cause, duration; the classified outcome and its reason code; retries and their reasons; the audit trail of who changed what |
| **The runnable** | Everything about the work itself: what it processed, which records it touched, why it made the decisions it made, its own progress and diagnostics — to its own log, with its own rotation and retention |

TaskControl answers *"did it run, and how did it end?"*. The runnable answers *"what did it
do?"*.

### Captured output is evidence, not the log

TaskControl continues to capture stdout and stderr, bounded and truncated as it already is.
Its purpose changes: it is **diagnostic evidence attached to an attempt**, useful when a job
fails and its own logging did not survive. It is not the operational log of record, and
nothing should be designed on the assumption that it is.

Practically: a task that needs its output preserved should write to its own log file. A task
whose entire purpose produces a few lines is well served by capture. Both are fine; only the
expectation changes.

Encouraging runnables to be wrapped in a script that handles their own logging is the
intended pattern, and it fits the portable capability package (ADR 0025) — a package carries
its `run.sh`, and that script owns its logging.

### The journal is a dispatch record

Given the boundary, the local journal written under `continue_with_local_journal` (ADR 0024)
is small and fixed: identifiers, revision, activation mechanism, times, exit status,
termination cause, and outcome. **It does not carry captured output.**

That is what makes it writable when things are already degraded. A journal that had to hold
arbitrary application output would be least likely to succeed exactly when it matters.

Format: line-delimited JSON, owner-readable only, under the data directory. One line per
activation, appended.

### When the journal write fails

The runnable has already run. Its side effects exist and cannot be withdrawn.

```text
runnable executes  ->  side effects are real
        |
journal write fails
        |
log CRITICAL to stderr, naming the task, revision, and outcome
        |
exit non-zero  ->  cron reports failure through its own mail/monitoring
        |
the gap is visible; reconciliation finds no record because none was written
```

TaskControl **does not** pre-write a journal entry before executing in availability-first
mode. Doing so would make a full disk stop the backups — the precise failure this mode exists
to survive.

Exiting non-zero is the honest signal: something ran and TaskControl cannot prove what. Cron's
own failure reporting is the escalation path, which is appropriate, because at that point
TaskControl's own machinery is what has failed.

### What this rules out

- Making TaskControl a searchable store of application log content.
- Sizing storage or retention around task verbosity rather than dispatch volume.
- A journal format that grows with what the task printed.
- Any design that assumes an operator reads a report's contents through TaskControl.

## Rationale

The boundary matches what production engineers already do, which is the product's stated
purpose. It also makes the hard case tractable: a small fixed-shape journal can be written
reliably under degradation, where a journal carrying arbitrary output could not.

It costs a demo-friendly feature — "see all your job output in one place" — in exchange for a
platform whose storage and reliability do not depend on code it does not own.

## Consequences

### Positive

- TaskControl's storage scales with dispatch volume, not with other people's verbosity.
- The journal is small enough to write when things are already failing.
- The division of labour is the one engineers already use, so the product fits their habits.
- Retention and privacy of detailed output stay with the task that produced it.

### Negative or accepted trade-offs

- An operator cannot read a report's contents through TaskControl. That must be documented
  plainly, because it is a reasonable thing to expect and will surprise people.
- Tasks that log nothing themselves are diagnosable only from bounded captured evidence.
- A future "logs" view in the UI must be presented as evidence, not as the task's log, or it
  will recreate the expectation this decision removes.

### Risks and mitigations

- Risk: the boundary erodes because capture is convenient — mitigation: output limits stay
  bounded, and the journal schema is fixed and carries no output field.
- Risk: an operator loses diagnosis because a task logs nothing and output was truncated —
  mitigation: truncation is recorded, and the recommended package pattern puts logging in the
  wrapper script.

## Implementation constraints

- The journal record has a fixed schema and contains no captured output.
- Journals are append-only, owner-readable only, and obey the same redaction rules as central
  logs — a degraded control plane does not relax the secret rules.
- Journal write failure logs `CRITICAL` and exits non-zero. It never silently continues.
- No pre-write gate in availability-first mode.
- Reconciliation is idempotent: ingesting one entry twice produces one execution record.

## Validation

A reviewer can confirm: the journal schema has no output field; a task whose journal cannot
be written exits non-zero with a `CRITICAL` line; documentation states plainly that
TaskControl is not the log of record; and captured output remains bounded.

## Migration and compatibility

No journals exist. Wave 3's capture behaviour is unchanged in code; only its documented
purpose changes, so no data migration is required.

## Future evolution and review triggers

Reconsider if operators consistently ask TaskControl to be their log store, which would be
evidence that the boundary is wrong for real use rather than merely unfamiliar — but the
answer then is likely an export integration, not moving the boundary.

## Rejected alternatives

Option A was rejected because it makes TaskControl's reliability and storage a function of
code it does not own, and because it would force the degraded-mode journal to carry arbitrary
output at exactly the moment writing must be most reliable.
