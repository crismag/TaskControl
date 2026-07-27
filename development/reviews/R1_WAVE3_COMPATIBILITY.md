# R1 — Wave 3 Compatibility Review

- Document level: **3 — Specifications**
- Lifecycle state: Canonical
- Wave: R1
- Date: 2026-07-27
- Baseline: `882bd53` (main, after the R0/R0.1 realignment)
- Method: **empirical.** Every claim below was produced by running the code, not by reading
  it. Where a finding is a demonstration, the command and its output are given.

## Purpose

ADR 0022 changed what activates recurring work. Waves 0–3 were built under the superseded
direction. This review establishes, on evidence, which of that code works under cron-backed
activation, which does not, and what must change before R2 can claim a working vertical
slice.

It is deliberately a review, not a refactor. Only the three changes the blueprint authorises
were made alongside it.

## Verdict

**Wave 3 is substantially reusable.** The execution services, outcome vocabulary, attempt
persistence, retry classification, and terminal-state guarantee all work unmodified from a
short-lived process. Nothing assumes a persistent scheduler.

Three things do not survive contact with cron-backed activation, and one of them is a
correctness problem rather than a naming one.

---

## Finding 1 — The overlap lock provides no protection. Demonstrated.

**Severity: correctness. Blocks R2 claiming overlap safety.**

ADR 0023 predicted this. It is now measured.

A task with `OverlapPolicy.FORBID` — the default — was activated by two concurrent
processes, as two cron activations would be:

```console
$ ( taskctl run slow-overlap-probe --json > a.json ) &
$ ( taskctl run slow-overlap-probe --json > b.json ) &
$ wait

  proc-a: succeeded    reason=None
  proc-b: succeeded    reason=None
```

Both executed the work:

```text
succeeded  attempts=1  stdout: START 3772281 | END 3772281
succeeded  attempts=1  stdout: START 3772285 | END 3772285
```

Two different process IDs, both running to completion, overlapping in time, with the
forbid-overlap policy in force. Neither was `BLOCKED`.

This is not a weaker guarantee than a durable claim. It is **no guarantee at all** between
activations, because `ProcessLocalOverlapLock` holds its state in a `dict` guarded by a
`threading.Lock` (`adapters/locking/process_local.py:52`), and two processes share neither.

The `OverlapLock` port and its contract tests are sound and carry forward. Only the
implementation is inert.

**Required before R2 can claim overlap safety:** the durable claim capability of ADR 0023.

---

## Finding 2 — The runtime cannot execute without the database. Blocks ADR 0024.

**Severity: architectural. Blocks the `continue_with_local_journal` path.**

`RuntimeService.run` reaches persistence before it can do anything at all:

| Line | Call | Needs the database |
|---|---|---|
| `service.py:144` | `self._load(request.task_id)` | yes — loads task and revision |
| `service.py:147` | `self._find_duplicate(...)` | yes |
| `service.py:167` | `self._persist_new(execution)` | yes |

The revision — which contains the action, the controls, and (after this wave) the activation
policy — is read *from the database*. So a cron-woken wrapper cannot learn what to run, or
even learn its own activation policy, without the control state that ADR 0024 assumes may be
absent.

ADR 0024's implementation constraint is explicit: *"A wrapper must decide from locally
deployed assets alone; it may not require the control plane to learn its own policy."* The
current shape cannot satisfy that.

**Required before R2 implements ADR 0024:** the cron wrapper must resolve its revision from a
locally deployed artefact — the task package, or a rendered snapshot written at apply time —
with the database used for *recording*, not for *deciding*. This is a real design task for
R2, not a rename.

---

## Finding 3 — Persistence failures leak internals to the operator.

**Severity: standards violation.**

With the database unreachable:

```console
$ taskctl run nightly-backup
╭───────── Traceback (most recent call last) ─────────╮
│ /mnt/.../site-packages/sqlalchemy/engine/base.py:144 │
...
OperationalError: (sqlite3.OperationalError) unable to open database file

$ echo $?
1
```

**43 lines** of traceback, including absolute filesystem paths and library internals.

`engineering/standards/21_API_AND_DATABASE_STANDARDS.md` requires: *"Do not expose stack
traces, secrets, internal paths, or vendor errors."* `standards/20` requires: *"Normalize
exceptions into domain-specific error types at adapter boundaries."*

Nothing wraps SQLAlchemy connection errors — confirmed by search: no `OperationalError`,
`DBAPIError`, or `SQLAlchemyError` handling exists anywhere in `src/`.
`create_database_engine` handles a missing driver but not a failure to connect.

The exit code **is** correct at `1`, so cron would see a failure rather than a false success.
That is the important half, and it works.

**Required:** wrap persistence errors at the repository or unit-of-work boundary into
`TransientInfrastructureError` / `PermanentInfrastructureError`. Not done in R1 — it is a
behaviour change beyond the three authorised, and it belongs with the R2 wrapper work that
must handle unreachable persistence deliberately anyway.

---

## Finding 4 — No field links an execution to its activation.

**Severity: gap, not defect. Shapes R2 and R5.**

`Execution` records `trigger_source`, `correlation_id`, and `idempotency_key`
(`domain/execution/execution.py:192–202`). It has no field identifying **which** cron
activation, or **which** work item, produced it.

For R2 this is tolerable: one managed cron entry maps to one task, so `trigger_source` plus
timing is enough to correlate. For R5 it is not — a work item must be traceable to the
execution that processed it and back.

The seam exists; the field does not. R5 should add it rather than overloading
`idempotency_key`, which means something else.

---

## What works, verified

### Execution services run correctly from short-lived processes

Two sequential, genuinely separate CLI invocations against one database:

```text
proc1: succeeded attempts=1
proc2: succeeded attempts=1
executions recorded: 2
unfinished: 0
```

Both recorded, both terminal, no residue. This is the core Wave 3 claim and it holds.

### Nothing assumes a persistent scheduler

Two `while True` loops exist, and both are bounded per execution:

- `subprocess_executor.py:239` — supervising one process until it exits or is terminated;
- `service.py:257` — the retry loop, bounded by `RetryPolicy.max_attempts`.

Neither is an activation loop. No timer, no polling for due work, no module-level mutable
state beyond the per-process secret registry in `infrastructure/logging.py`, which is
correctly per-process.

### Persistence works across independent invocations

Proven by Wave 2's restart-durability tests and re-confirmed above: a task written by one
process is read by another, with digests verifying.

### Configuration resolves from the revision

`_resolve_environment` (`service.py:~330`) uses only `revision.action.environment` plus
per-request overrides. It refuses secret references rather than inventing values. Once the
revision itself is locally available (Finding 2), configuration resolution needs no control
plane.

---

## Naming that encodes the superseded model

Corrected in this wave:

| Location | Was | Now |
|---|---|---|
| `src/taskcontrol/__init__.py` | "schedules and runs work itself through an internal scheduler; does not write to any host scheduler configuration" | cron-backed description |
| `domain/execution/execution.py` | `TriggerSource.SCHEDULE` — "the internal scheduler reached an occurrence" | "cron activated a managed artefact" |
| `application/runtime/service.py` | module docstring names "the internal scheduler" as a future caller | cron wrapper, queue worker, run-now |
| `application/runtime/__init__.py` | same | same |
| `docs/DEVELOPMENT.md` | `taskctl run` presented as an ordinary workflow | already corrected in R0 |

Deferred deliberately: **renaming `Task` to `Capability`.** ADR 0025 maps the vocabulary and
notes the decision belongs here. The recommendation is **do not rename yet**. The concepts
are correct; only the labels lag. Renaming touches every module, every test, the storage
schema, and the published JSON Schema, and it would collide with the R2 work that is about to
add fields to the same classes. Revisit once R2 has settled the revision shape, when the
churn is smaller and the naming is informed by a working cron slice.

---

## Changes made in this wave

Only the three the blueprint authorises:

1. The five misleading docstrings above.
2. `ProcessLocalOverlapLock` demoted to a test double, with a test asserting no production
   path constructs it.
3. `activation_policy` added to the revision, defaulting to `require_control_state`.

No Wave 3 capability was deleted. No behaviour changed beyond items 2 and 3.

---

## Consequences for R2

R2 cannot deliver a working cron slice without also delivering:

1. **Durable claims** (ADR 0023) — otherwise the slice ships with the overlap defect
   demonstrated in Finding 1, on the very path where cron makes it certain rather than
   unlikely.
2. **Locally resolvable revisions** (Finding 2) — otherwise ADR 0024's availability-first
   mode cannot be implemented at all.
3. **Wrapped persistence errors** (Finding 3) — otherwise the first thing an operator sees
   when the database is down is a SQLAlchemy traceback.

The blueprint already lists the first. The second and third should be added to R2's build
list before it starts.
