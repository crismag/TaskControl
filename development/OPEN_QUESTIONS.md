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

- **Status:** Open
- **Raised:** 2026-07-26, as a consequence of ADR 0018
- **Blocks:** nothing yet; shapes Wave 5

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
