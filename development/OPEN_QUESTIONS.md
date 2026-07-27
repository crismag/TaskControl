# Open Questions

- Document level: **supporting**
- Lifecycle state: Canonical (register of Open decisions)
- Rule: an unresolved choice lives here, never as ambiguous prose in a canonical document (ADR 0017)

## How to use this file

Add a question when a decision is genuinely unresolved and proceeding either way would be a guess with lasting consequences. Do not add a question to avoid making a routine judgement call.

Each entry states what is undecided, who or what it blocks, the options, and a recommendation. When a question is resolved, record the answer in the document it affects — or an ADR if it is Level 0 or Level 1 — and remove the entry with a note in the pull request.

Status values: **Open**, **Blocking** (work cannot proceed), **Resolved** (pending removal).

---

## Q1 — Repository licence

- **Status:** Open
- **Raised:** 2026-07-26, during canonicalization
- **Blocks:** publishing the repository; any external contribution; the `LICENSE` file that Wave 0 would otherwise add

No licence has been chosen, so the repository is all-rights-reserved by default. Wave 0 can complete without it, but the repository cannot be shared or accept contributions until it is settled.

Options considered:

| Option | Effect |
| --- | --- |
| Apache-2.0 | Permissive with an explicit patent grant. Adopted without legal review by most companies. Best fit for a product whose strategy depends on third-party plugins, adapters, and integrations. |
| MIT | Shortest and most permissive; no patent grant. |
| AGPL-3.0 | Copyleft extending to network use. Protects against a hosted competitor, but many organisations prohibit AGPL software internally, which would work against the integration ecosystem `product/INTEGRATION_STRATEGY.md` describes. |
| Proprietary | Retains all rights. Incompatible with the public-integration positioning unless that positioning changes. |

**Recommendation:** Apache-2.0, on the grounds that `product/INTEGRATION_STRATEGY.md` and `product/ECOSYSTEM_BOUNDARIES.md` both commit to an external-consumer ecosystem, which a copyleft or proprietary licence would suppress.

**Deferred by:** repository owner, 2026-07-26.

---

## Q2 — Persistent-process requirement in Phase 1

- **Status:** **Resolved** by ADR 0022 (2026-07-27) — pending removal
- **Resolution:** the question is moot. Cron owns recurring activation, so TaskControl needs
  no persistent process for scheduled work. The concern that prompted this question is
  exactly what drove the realignment.
- **Raised:** 2026-07-26, as a consequence of ADR 0018 (now superseded)
- **Blocks:** nothing

ADR 0018 puts the internal scheduler in Phase 1, which means TaskControl must run as a persistent process to trigger scheduled work. The original cron-generation design had no such requirement: a generated crontab entry runs whether or not TaskControl is up.

`product/USERS_AND_USE_CASES.md` names "individual developers and administrators running recurring automation" as primary users. It is not established whether those users will accept running a daemon, or whether they expect the tool to install schedules and get out of the way.

Options:

- Accept the persistent process for Phase 1 and document it plainly. Misfire policy and restart catch-up (already Wave 5 requirements) make it survivable.
- Bring a minimal cron-artefact generator forward into Phase 1 purely as a trigger mechanism, deferring plan/apply/drift. This partially reverses ADR 0018.
- Ship a systemd user unit in Wave 10 so the persistent process is managed by the host and the requirement becomes invisible in practice.

**Recommendation:** the first option, plus the third in Wave 10. Revisit only if a real user rejects the daemon model.

---

## Q3 — Approvals in the Phase 1 boundary

- **Status:** Open
- **Raised:** 2026-07-26, during canonicalization
- **Blocks:** nothing yet; shapes Wave 10

`product/PRODUCT_SCOPE.md` lists "approvals and controlled operational actions" in the base product, and `PRODUCT_ROADMAP.md` Phase 1 repeats it. The retired roadmap placed approvals at Wave 9 alongside enterprise features, and `domain/06` specifies them with roles and delegation that Phase 1 does not have.

An approval workflow with exactly one administrator, no roles, and no delegation is close to a no-op: the person requesting is the person approving. Either Phase 1 needs a second identity for approvals to mean anything, or approvals should follow authentication into Phase 2.

Options:

- Keep approvals in Wave 10 as a revision-bound state machine that works correctly once identities exist, and accept that it is degenerate with one user.
- Move approvals to Phase 2, immediately after authentication, and remove them from the Phase 1 scope statement.

**Recommendation:** the second, but it edits a Level 0 document and therefore needs the owner's decision rather than mine. Wave 10 currently implements the first.

---

## Q4 — Dependency model boundary

- **Status:** Open
- **Raised:** 2026-07-26, from `product/USER_JOURNEYS.md` Journey 8
- **Blocks:** nothing yet; shapes Wave 5

Phase 1 includes "dependency eligibility": a task may require that an upstream task succeeded recently. Journey 8 warns against becoming a general-purpose pipeline orchestrator, and `product/PRODUCT_SCOPE.md` does not name DAG scheduling.

The boundary between "simple dependency check" and "workflow engine" is not defined. Undefined, it will drift outward one feature request at a time.

Proposed boundary for Wave 5, to be confirmed:

- A dependency is a **precondition evaluated at trigger time**, never a scheduling instruction.
- TaskControl does not order, queue, or trigger a downstream task because an upstream one finished.
- Supported: "upstream task X most recently succeeded within N hours".
- Not supported: fan-in, fan-out, conditional branching, dynamic graphs, or backfill.

**Recommendation:** adopt the boundary above as written, and require an ADR to widen it.

---

## Q5 — Managed cron block granularity

- **Status:** Open
- **Raised:** 2026-07-27, during the cron-backed realignment
- **Blocks:** blueprint R2 design

Should TaskControl manage **one block containing all managed entries**, or **one block per
task**?

| Option | For | Against |
|---|---|---|
| Single block | One region to find, parse, and verify; simple identity | Every task change rewrites the whole block; two concurrent applies conflict over unrelated tasks |
| Per-task block | Changes are isolated; concurrent applies to different tasks do not conflict | More markers in the crontab; more parsing surface; a partially applied set is harder to reason about |

**Recommendation:** per-task blocks with a stable identifier, because isolation matters more
than tidiness once more than a handful of tasks exist. Needs deciding before R2 renders
anything, since it determines the identity scheme and the fail-closed rule.

---

## Q6 — Which crontab TaskControl manages

- **Status:** Open
- **Raised:** 2026-07-27
- **Blocks:** blueprint R2

A user crontab, the system crontab, `/etc/cron.d` drop files, or a configurable choice? Each
has different permission requirements, different `PATH` and shell semantics, and different
implications for which user the task runs as.

`/etc/cron.d` files are attractive for per-task isolation (see Q5) but require root and
carry stricter filename rules. A user crontab needs no privilege but cannot express the
execution user.

**Recommendation:** support the user crontab first, since it needs no privilege and suits a
single-user installation, and treat `/etc/cron.d` as the multi-user path in a later wave.
Must be decided explicitly rather than inherited from whatever R2 implements first.

---

## Q7 — Local journal format and location

- **Status:** Open
- **Raised:** 2026-07-27, as a consequence of ADR 0024
- **Blocks:** blueprint R2 (the `continue_with_local_journal` path)

ADR 0024 requires a local journal when a task runs with central persistence unavailable. It
does not settle the format, the location, the rotation policy, or the permissions — and all
four matter, because the journal may contain command output.

Open sub-questions: line-delimited JSON or a small SQLite file; a path under the data
directory or a configurable one; who may read it; how long it is kept once reconciled; and
what happens when the journal itself cannot be written, which is the case where the runnable
has already produced side effects.

**Recommendation:** line-delimited JSON under the data directory with owner-only permissions,
because it needs no library and survives partial writes better than a database — but the
unwritable-journal case needs a deliberate answer before R2.

---

## Q8 — Registered task types for remote submission

- **Status:** Open
- **Raised:** 2026-07-27
- **Blocks:** blueprint R5

The submission API accepts a *registered task type*, never an arbitrary command. What
registers a type, and who may submit to it, is unresolved.

Open sub-questions: whether a task type is simply an existing task definition or a distinct
concept; whether a payload schema is declared and validated per type; whether authorisation
is per type or global; and how a caller discovers which types exist.

**Recommendation:** a work-item task type is an existing task revision explicitly marked
submittable, with a declared payload schema. That reuses the definition model rather than
inventing a parallel one, and makes "what can be submitted" reviewable in the same place as
everything else about the task.
