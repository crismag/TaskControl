# TaskControl

**TaskControl automates the work of production engineers, not just the execution of scripts.**

If you keep production running, you already have a crontab. What you do not have is a record
of why each line exists, who owns it, whether it ran last night, whether the file it points at
is still the one somebody reviewed, or which of the last thirty runs quietly did nothing.

TaskControl adds that layer without taking cron's job away. **Cron activates. TaskControl
governs.** Your recurring work keeps running when TaskControl's API and database are down —
that is a property of the design, not a hope.

## What it looks like

Here is a crontab most engineers would recognise. Four jobs, one comment, no idea what the
first three actually do:

```crontab
# log rotation, unrelated to TaskControl
0 5 * * * root /usr/sbin/logrotate /etc/logrotate.conf

# backups -- do not touch, ask Dave
0 2 * * * root /opt/ops/bin/backup-db.sh
30 17 * * 1-5 root /opt/ops/bin/settlement-report.sh >> /var/log/settlement.log 2>&1
15 3 * * * root /opt/ops/bin/prune-scratch.sh
```

You describe those three as capabilities — what they are for, who owns them, how they should
be deployed — and then:

```console
$ taskctl schedule plan
3 change(s) to apply:

  CREATE     nightly-database-backup
             /etc/crontab
             No managed artefact exists for this capability yet.
  CREATE     settlement-report
             /etc/cron.d/settlement-report
             No managed artefact exists for this capability yet.
  CREATE     prune-scratch-volume
             /etc/cron.daily/prune-scratch-volume
             No managed artefact exists for this capability yet.

$ taskctl schedule apply
Applied 3 change(s) and verified each one.
```

Afterwards, your crontab says what it is doing — and the log-rotation line you did not hand
over is byte-for-byte where it was:

```crontab
# log rotation, unrelated to TaskControl
0 5 * * * root /usr/sbin/logrotate /etc/logrotate.conf

# >>> taskcontrol block >>>
# Managed by TaskControl. Edits between the markers are overwritten on the next apply.
# taskcontrol task=nightly-database-backup id=task_019fa44d-e4c9-7cd9-952c-1d72fa069982 digest=sha256:5775128...
# Dump the trading database and prune anything older than 14 days.
0 2 * * * root /usr/local/bin/taskctl activate nightly-database-backup
# <<< taskcontrol block <<<
```

The settlement report needed to run as a service account, so it went to `/etc/cron.d`, which
is the layout that can say so:

```crontab
# >>> taskcontrol task=settlement-report id=task_019fa44d-e4cd-73ad-a6e1-8b1b4d128877 digest=sha256:7b059fd... >>>
# Managed by TaskControl. Edits between the markers are overwritten on the next apply.
# Publish the daily settlement reconciliation for the finance team.
30 17 * * 1-5 settlement /usr/local/bin/taskctl activate settlement-report
# <<< taskcontrol task=settlement-report <<<
```

And the scratch cleanup was simply "a daily job", so it went where the operating system
already puts daily jobs — `/etc/cron.daily` — without anyone choosing a layout.

Six months later, somebody edits one by hand at 2am. You find out:

```console
$ taskctl schedule verify
Checked 3 artefact(s); found drift:

  MODIFIED   /etc/cron.d/settlement-report
             The deployed artefact differs from the published revision. Somebody edited it
             by hand, or it was deployed from a different revision.

$ echo $?
1
```

Exit code 1, so you can run that from monitoring rather than remembering to look.

## What you get that cron does not give you

- **Every run recorded** — with an outcome that distinguishes success from a skip, a block,
  a timeout, a cancellation, an external kill, and a result nobody can prove.
- **No overlapping runs**, enforced by a durable claim in the database rather than by hoping
  the last run finished.
- **Ownership, purpose, and history** attached to the job rather than to a comment above it.
- **Drift detection**, so a hand-edited crontab is something you find rather than something
  you discover during an incident.
- **Versioned definitions.** A published revision never changes; a correction is a new one,
  so an execution from eight months ago still means what it meant.
- **Deployment that is reviewable**: plan before apply, verify by reading back, roll back on
  failure, and never touch a line TaskControl did not write.

## What happens when TaskControl is down

Your jobs still run, because cron is what activates them.

Each capability says what to do when its control plane is unreachable. A backup declares
`continue_with_local_journal` — run anyway, record locally, reconcile later. A settlement run
declares `require_control_state` — do not run at all rather than run unrecorded, and exit 75
so the failure is visible. Neither decision is guessed at 2am: both are installed on the host,
next to the artefact, before they are ever needed.

```console
# database down, backup declared availability-first
$ /etc/cron.daily/prune-scratch-volume; echo $?
0

# database back
$ taskctl reconcile
Recorded 1 journalled activation(s); 0 were already known.
```

## The problem

Cron does its job well. What gets lost is everything around it — why a task exists, who owns it, where its runnable lives, whether the installed schedule still matches what anyone intended, what was retried, and what needs a human. TaskControl supplies that missing layer without taking cron's job away.

## Core capabilities

- Define reusable, versioned tasks with schedules expressed as "every weekday at 06:00" — no cron syntax required.
- Generate, plan, apply, and verify **managed cron artefacts**, preserving unmanaged entries.
- Import and adopt an existing cron estate without rewriting it.
- Register drop-in runnable packages from approved directories.
- Track ownership, purpose, runbooks, criticality, and review status.
- Record attempts, outcomes, logs, history, and audit evidence — distinguishing success from a skip, a block, a timeout, and an unproven result.
- Accept durable asynchronous work from remote systems, processed by cron-woken workers.
- Operate through a CLI, REST API, and web application.
- Extend through plugins, adapters, events, and webhooks.

## Example uses

TaskControl can support:

- system administration and maintenance jobs;
- report generation and data-processing pipelines;
- CI/CD and release operations;
- engineering and semiconductor automation flows;
- adopting and documenting an existing cron estate;
- scheduled business processes;
- application-to-application orchestration;
- media, rendering, and batch-processing jobs;
- AI agent and KAE workflows as optional integrations.

## Architectural boundary

```text
        Users, administrators, and remote applications
                            |
              Web UI  /  CLI  /  REST API
                            |
                 TaskControl control plane
                            |
        +-------------------+--------------------+
        |                                        |
 Scheduled task management              Async work submission
        |                                        |
 Cron artefact plan/apply                 Durable work queue
        |                                        |
        v                                        v
      cron  ------------ wakes ------->  short-lived worker
        |                                        |
        +-------------------+--------------------+
                            v
                  Durable claim / lease
                            v
                    Execution services
                            v
              Outcomes, attempts, logs, audit
```

The control plane is optional at activation time. Cron wakes the work; TaskControl records and governs it.

TaskControl Core must remain independent of any specific business domain, AI framework, or external product. Integrations such as KAE, GitHub, CI/CD platforms, notification services, and infrastructure tools connect through stable public contracts.

## Current project stage

**Early implementation, and honest about it.** Waves 0–3 built the foundation, domain model, persistence, and execution services under a previous internal-scheduler direction. That direction is superseded: cron now owns recurring activation ([ADR 0022](development/decisions/0022_CRON_BACKED_ACTIVATION.md)), and the execution services were kept and repositioned rather than rewritten.

Everything shown above runs. Nothing in this README is aspirational — the crontabs and command output are copied from a real run, not written by hand.

```bash
make install && make check
.venv/bin/taskctl health
```

See [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) to get set up, and the [implementation blueprint](development/10_IMPLEMENTATION_BLUEPRINT.md) for what is being built next.

### What works today, and what does not

Working now: capability definitions with immutable revisions, managed cron deployment across
four layouts with plan, apply, verify, drift detection and rollback, locally installed
revisions, activation policy under a failed control plane, local journalling and
reconciliation, durable cross-process overlap protection, execution history, a CLI, and a
REST health surface.

Not yet: a web interface, remote hosts, the durable work queue and its workers, expected-
outcome evaluation (a process exiting zero is currently taken at its word), REST and MCP
surfaces beyond health, and adopting an existing crontab by importing it rather than
redefining it.

## Development documentation

Start with [`development/00_CONTEXT_INDEX.md`](development/00_CONTEXT_INDEX.md). It is the only entry point: it carries the file map, the documentation levels, the precedence ladder, and the current status.

- What we build next: [`development/10_IMPLEMENTATION_BLUEPRINT.md`](development/10_IMPLEMENTATION_BLUEPRINT.md)
- Product identity and boundaries: [`development/product/`](development/product/)
- Why every file exists: [`development/DOCUMENTATION_AUDIT.md`](development/DOCUMENTATION_AUDIT.md)

## Product direction

TaskControl is developed first as a useful standalone, cron-backed application. Distributed, enterprise, and ecosystem capability is added incrementally, and never at the cost of the guarantee that already-deployed recurring work keeps running without TaskControl.

## Licence

Not yet chosen — see [`OPEN_QUESTIONS.md`](development/OPEN_QUESTIONS.md) Q1. Until it is, all rights are reserved and the repository is not open for external contribution.
