# Example capabilities

Three definitions of work a production engineer already does by hand. They are not a tour of
the data model — each one exists to show a decision you will actually have to make, and what
TaskControl does with your answer.

Every file here round-trips through the real serialiser, and a test in CI fails if one stops
matching what the code accepts. If an example is wrong, the build says so.

| File | The decision it shows |
|---|---|
| [`nightly-database-backup.yaml`](nightly-database-backup.yaml) | Missing a run is worse than missing the record of it |
| [`settlement-report-task.yaml`](settlement-report-task.yaml) | An unrecorded run is worse than a missed one — and the work needs its own service account |
| [`prune-scratch-volume.yaml`](prune-scratch-volume.yaml) | It is just a daily job, and you would rather not think about layout at all |

## Nightly database backup — availability first

Declares `activation_policy: continue_with_local_journal`. When TaskControl's database is
unreachable at 2am, cron has already fired and the wrapper has to decide something. This
capability says: **run anyway.** The run is recorded to a local journal and reconciled when
the control plane returns.

Two consequences worth knowing before you copy this, because neither is hidden:

- A degraded run has **no overlap protection**. The claim that prevents two backups running
  at once lives in the database that is unreachable. The journal entry says so.
- A capability that needs a secret cannot run this way at all. Manifests carry secret
  *references*, never values, so there is nothing to resolve locally — it refuses rather than
  running with a quietly incomplete environment.

Deployed as `crontab_single_block` into the system crontab: one managed region holding every
entry, which is what you want when you would rather read your managed jobs in one place.

## Settlement report — record first

Declares `activation_policy: require_control_state`, the default. With the control plane
unreachable it **does not run**, and exits 75 so cron reports a failure you can see. For
regulated or financial work, an unrecorded run is the expensive outcome: somebody re-runs it
by hand because nothing proves it happened.

It also runs as the `settlement` service account, which is why it is deployed as
`cron_d_file`. A user crontab cannot express an execution user, so asking for one there is
rejected at validation rather than silently running the job as somebody else.

## Prune scratch volume — classified, not configured

Carries `classification: daily` and **no schedule at all**. The directory is the schedule: it
lands in `/etc/cron.daily` as an executable script, where the operating system already runs
daily jobs.

This is the common case, and it is meant to be boring. "Run this daily" should not require an
opinion about crontab layout.

## Applying them

```console
$ taskctl schedule plan     # shows what would change; writes nothing
$ taskctl schedule apply    # writes, then reads back and verifies each artefact
$ taskctl schedule verify   # exits 1 on drift, so monitoring can run it
```

Unmanaged entries in your crontab are never touched — not reordered, not reformatted. Only
content between TaskControl's markers is ever rewritten.
