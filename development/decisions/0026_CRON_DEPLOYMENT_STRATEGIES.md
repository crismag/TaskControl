# ADR 0026: Cron Deployment Is a Configurable Strategy, Not One Layout

- Document level: **1 — Architecture**
- Lifecycle state: Canonical
- Status: Accepted
- Date: 2026-07-27
- Owners: TaskControl maintainers
- Supersedes: None
- Superseded by: None
- Related documents: ADR 0010, ADR 0022, ADR 0025, `development/product/OPERATIONAL_MODEL_AND_PRODUCT_INTENT.md`, `development/OPEN_QUESTIONS.md` Q5 and Q6

## Context

R2 must render managed cron artefacts, and two questions blocked it: how managed entries are
marked in a crontab, and which crontab is managed. Both were posed as a choice between
options.

Both framings were wrong. Real estates already use several layouts simultaneously, and which
one is right depends on the task, not on the product:

- **run-parts directories.** `/etc/cron.hourly`, `/etc/cron.daily`, and friends hold
  executable scripts run by a system-defined schedule. An operator drops a file in and the
  system takes care of the rest. This is the layout the product's own historical background
  names first, and it maps directly onto the drop-in package model.
- **One managed block per task.** A marked region per task, in a crontab. Changes are
  isolated; two concurrent applies to different tasks do not contend.
- **One managed block for all entries.** A single region holding every managed line. Tidier
  to locate, and appropriate for a small estate managed as a unit.

An operator with sixty jobs will want daily cleanups in `/etc/cron.daily`, a market-close job
as its own block with a precise schedule, and a handful of small related jobs grouped
together. Forcing one layout on all three would make TaskControl less useful than the
crontab it replaced.

The same applies to the target. A single-user installation wants a user crontab and no
privilege. A multi-user host needs `/etc/cron.d` to express the execution identity. Neither
is the default for the other.

## Decision drivers

- Real estates mix layouts; a product that permits one will be worked around.
- The layout is a property of the task, or of a class of tasks — not of the installation.
- Execution identity is only expressible in some layouts, so the layout choice has semantics,
  not just aesthetics.
- Whatever is chosen must be deterministic, verifiable by read-back, and safe alongside
  unmanaged content.

## Considered options

### Option A — Pick one layout and one target

Simplest to build. Wrong for most estates, and the workaround is an operator editing crontabs
by hand — the exact behaviour the product exists to remove.

### Option B — A deployment strategy, selected per task

More surface to build and test. Matches how estates actually work, and makes the choice a
reviewable property of the definition.

## Decision

Adopt **Option B**. Cron deployment is governed by a **deployment strategy**, a property of
the task revision, defaulting sensibly and overridable per task or per classification.

### The strategies

| Strategy | Artefact | Expresses execution user | Typical use |
|---|---|---|---|
| `run_parts_directory` | An executable file in `/etc/cron.daily` and similar | no — runs as the directory's configured user | Classified periodic work: hourly, daily, weekly |
| `crontab_block_per_task` | A marked region per task in a crontab | only in system crontab or `cron.d` | Tasks with specific schedules, changed independently |
| `crontab_single_block` | One marked region holding all managed lines | as above | Small estates managed as a unit |
| `cron_d_file` | One file per task in `/etc/cron.d` | **yes** | Multi-user hosts; tasks needing a service account |

### The targets

Strategy and target are related but distinct. A target is *where* the artefact lands:

| Target | Privilege | Execution identity |
|---|---|---|
| `user_crontab` | none | the invoking user only |
| `system_crontab` | root | expressible |
| `cron_d` | root | expressible |
| `run_parts` | root | the directory's configured user |

Not every combination is valid — `run_parts_directory` implies a `run_parts` target, and
`cron_d_file` implies `cron_d`. Validation rejects an invalid pairing **before** anything is
written, with an explanation, rather than producing an artefact that silently does something
else.

### Classification

Tasks may carry a **classification** — `hourly`, `daily`, `weekly`, `monthly` — which
supplies a default strategy and target. A task classified `daily` with no explicit strategy
deploys as a `run_parts_directory` artefact in `/etc/cron.daily`. An explicit strategy on the
task always wins.

Classification is how an operator expresses "this is just a daily job" without choosing a
layout, and it is what makes the common case require no decision at all.

### Defaults

- Unclassified task, no explicit strategy: `crontab_block_per_task` into `user_crontab`.
  This needs no privilege, works on a single-user install, and isolates changes.
- Classified task: the classification's strategy, which for the periodic classifications is
  `run_parts_directory`.

The defaults are chosen so that the zero-privilege path is what an operator gets without
asking, and so that the most common shape of operational work — "run this daily" — maps onto
the layout the operating system already provides for it.

### Rules that hold for every strategy

1. **Unmanaged content is never modified.** Not reordered, not reformatted, not touched.
2. **Managed artefacts carry a stable identifier** naming the task and its revision.
3. **Plan before apply.** A plan shows additions, changes, removals, and unchanged artefacts.
4. **Verify by read-back.** After writing, read the artefact back and compare.
5. **Fail closed on ambiguous identity.** Two regions claiming the same task, a malformed
   marker, or a `cron.d` file whose name does not match its content is an error, never a
   guess.
6. **Rollback on failed apply**, restoring the previous state exactly.
7. **Rendering is deterministic.** The same revision renders byte-identically every time.

### Filename constraints

`run_parts` and `cron.d` both restrict filenames — run-parts under `--lsbsysinit` rules
rejects names containing a dot, and `cron.d` ignores files with unexpected characters. A task
whose slug cannot produce a valid filename is rejected at validation with the reason, not at
deployment with silence.

## Rationale

The layout question has no single right answer because it is not TaskControl's question. It
belongs to the task, and to the operator who knows whether this is "a daily cleanup" or "the
market-close job that runs as `settlement` at 17:30". Modelling it as a strategy makes that
choice explicit, reviewable, and versioned with the revision that carries it.

Supporting run-parts from the start also honours the product's own history: drop a file in a
directory and let the system run it is the oldest and most widely understood shape of
operational automation, and it is exactly what the drop-in package model already produces.

## Consequences

### Positive

- Estates keep the layouts they already use.
- Classification makes the common case decision-free.
- Execution identity becomes expressible where the layout supports it.
- Drop-in packages and run-parts deployment reinforce each other.

### Negative or accepted trade-offs

- Four strategies and four targets is materially more to build, verify, and roll back than
  one. R2 is larger as a result.
- Each strategy has its own read-back and drift semantics; a bug in one is not a bug in all,
  which cuts both ways.
- Privileged targets need a privilege story that a single-user install does not, so R2 must
  degrade clearly when it cannot write where it was asked to.

### Risks and mitigations

- Risk: partial support — one strategy well built and three shallow — mitigation: shared
  contract tests every strategy must pass, as with executors.
- Risk: an operator picks a strategy that cannot express what they need, such as an execution
  user in a user crontab — mitigation: validation rejects the combination with the reason
  before writing.
- Risk: run-parts filename rules produce a silently ignored file — mitigation: validated at
  definition time, and read-back verification confirms the system actually sees it.

## Implementation constraints

- Strategy and target belong to the task revision and are therefore versioned and immutable
  once published.
- The domain names strategies; the cron adapter implements them. No domain module contains
  crontab syntax.
- Every strategy passes the same contract tests: deterministic render, unmanaged preservation,
  idempotent re-apply, update, disable, remove, read-back verification, ambiguous-identity
  rejection, and rollback.
- Tests use temporary files and directories. A test that writes to a real system crontab or
  `/etc/cron.d` is not acceptable.

## Validation

A reviewer can confirm: each strategy has contract tests; an invalid strategy/target pairing
is rejected with an explanation; unmanaged content is byte-identical after every operation;
and a classified task with no explicit strategy deploys where its classification says.

## Migration and compatibility

No artefacts are deployed anywhere yet. The revision schema gains strategy, target, and
classification fields, defaulted so an existing definition remains valid.

## Future evolution and review triggers

Reconsider when a non-cron scheduler adapter arrives — systemd timers have their own layout
question, and the strategy concept should generalise rather than being duplicated per
scheduler.

## Rejected alternatives

Option A was rejected because estates that mix layouts would either be unable to adopt
TaskControl or would work around it by hand-editing crontabs, which is the failure the
product exists to remove.
