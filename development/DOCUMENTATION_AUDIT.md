# Documentation Audit

- Document level: **supporting**
- Lifecycle state: Canonical
- Audit date: 2026-07-27 (updated after the cron-backed realignment, R0)
- Performed during: the repository canonicalization PR; revised by realignment wave R0
- Policy: ADR 0017

## Purpose

A complete inventory of every document, its lifecycle state, and why it exists. This is the file a maintainer reads to understand the shape of the repository without opening 90 files. It is updated whenever a document changes state.

## Lifecycle states

| State | Meaning |
| --- | --- |
| **Canonical** | Current source of truth. Governs implementation. |
| **Superseded** | Replaced by a named successor. Retained for historical reasoning. |
| **Archived** | Historically important, no longer descriptive of any plan. |
| **Future** | Correct and wanted, deliberately outside current scope. Not obsolete. |
| **Open decision** | Unresolved choice, held in `OPEN_QUESTIONS.md`. |

## Realignment R0 — 2026-07-27

The product direction changed: cron owns recurring activation (ADR 0022). Documents changed
in this reconciliation, all in place rather than as a new package:

| File | Change |
|---|---|
| `/README.md` | Rewritten around cron-backed identity and the new architecture diagram |
| `product/PRODUCT_VISION.md` | Rewritten: north star, six pillars, responsibility boundary, product test |
| `product/PRODUCT_SCOPE.md` | Rewritten: cron management in scope, activation out of scope, queue limits stated |
| `product/PRODUCT_ROADMAP.md` | Rewritten: Phase 1 is cron-backed managed tasks; Phase 2 is remote submission |
| `product/PRODUCT_PHILOSOPHY.md` | "Two delivery modes" replaced by "how intent becomes activation" |
| `product/USER_JOURNEYS.md` | Journey 1 corrected; 15 promoted to Phase 1; 16 and 17 added |
| `product/USERS_AND_USE_CASES.md` | Cron-literacy standard; async submission |
| `product/INTEGRATION_STRATEGY.md` | Async submission; prohibition on arbitrary shell submission |
| `architecture/ARCHITECTURE_OVERVIEW.md` | Process model added; activation flow separated from execution flow; topologies replaced |
| `domain/README.md` | Terminology table correcting schedule, trigger, execution, runtime, dependency, claim |
| `domain/02_`, `domain/04_`, `domain/05_` | Cron-backed reading notes at the head of each |
| `10_IMPLEMENTATION_BLUEPRINT.md` | Old Wave 4 stopped; R0–R5 introduced; Waves 0–3 retained with honest provenance |
| `future/DEFERRED_CAPABILITIES.md` | Cron generation, crontab import, and durable locking promoted to Phase 1 |
| `OPEN_QUESTIONS.md` | Q2 resolved; Q5–Q8 added (cron block granularity, crontab target, journal format, task types) |
| `00_CONTEXT_INDEX.md` | Status, authority map, and file map updated |
| `decisions/0018_*`, `decisions/0021_*` | Marked **Superseded** with banners; reasoning retained |
| `decisions/0022_*`, `0023_*`, `0024_*` | **New** |
| `realignment/README.md` | Marked **Historical — provenance only** |
| `docs/DEVELOPMENT.md` | Run-now reframed as administrative; overlap protection stated as not in force |

Deliberately **not** changed: Wave 3 source code. R0 was documentation-only; the four source
docstrings still asserting the old direction are itemised in blueprint R1.

## Realignment R0.1 — 2026-07-27

The owner supplied the operational model and design vision, then refined the domain model:
two kinds of activation rather than five sources, the queue as infrastructure rather than a
source, and **Operational Capability** as the primary concept in place of "operational work".

| File | Change |
|---|---|
| `decisions/0025_OPERATIONAL_CAPABILITY_AND_ACTIVATION_MODEL.md` | **New.** Capability/request/instance; activation policy vs mechanism; transport independence; distribution ready but not built |
| `product/PRODUCT_DESIGN_VISION.md` | Owner's refinement appended, original text preserved; principles 1 and 9 updated |
| `product/PRODUCT_VISION.md` | North star re-cut around capability lifecycle; pillars and principles reordered; two kinds of activation |
| `product/PRODUCT_PHILOSOPHY.md` | "TaskControl automates the work of production engineers, not just the execution of scripts" becomes the primary rule; portable capability packages added |
| `product/PRODUCT_SCOPE.md` | Capability-centred; transports as adapters; queue as infrastructure; distribution architecture-ready but deferred |
| `product/INTEGRATION_STRATEGY.md` | Transport-independence rule stated as governing; MCP named as an adapter |
| `product/PRODUCT_ROADMAP.md` | Transports are not roadmap features; Phase 2 renamed to on-demand activation; Phase 3 distribution gated on real need |
| `architecture/ARCHITECTURE_OVERVIEW.md` | Conceptual model layered capability → policy → mechanism → execution → observation; distribution-readiness section |
| `domain/README.md` | Capability, execution request, execution instance, activation policy and mechanism, queue — each mapped to current code names |
| `10_IMPLEMENTATION_BLUEPRINT.md` | R5 leads with the application service so transports stay adapters; transport adapters excluded from waves |
| `00_CONTEXT_INDEX.md` | Identity, authority map, and status updated |

**Corrections to R0.** R0's "cron-backed" north star put infrastructure in the subject
position, and its five-activation-source list treated the queue as a source. Both are
superseded by ADR 0025. R0's cron mechanics, durable claim, and activation policy stand.

An earlier suggestion to move multi-server work earlier was **wrong** and is withdrawn: the
architecture stays ready, the implementation stays single-machine until a real requirement
arrives.

## Post-realignment changes — 2026-07-27

| File | Change |
|---|---|
| `product/PRODUCT_PHILOSOPHY.md` | **Recognition test** added: can a production engineer who has never seen TaskControl immediately recognise it as automating work they do by hand? States when the test is *failed*, not merely unmet |
| `engineering/governance/40_DEFINITION_OF_DONE.md` | Recognition test applied to any user-visible change |
| `10_IMPLEMENTATION_BLUEPRINT.md` | Recognition test added as a Phase 1 exit criterion alongside the functional ones |
| `docs/DEVELOPMENT.md` | PostgreSQL setup documented for both a local server and Docker, with the dedicated-database warning |
| `.github/workflows/ci.yml` | PostgreSQL 16 service on every push, plus a step that **fails the build if the PostgreSQL tests skip** |

Code changed in the same period, outside the documentation-only scope of R0 and R0.1, because
running the PostgreSQL suite for the first time exposed defects rather than gaps:

| File | Change |
|---|---|
| `migrations/versions/0002_executions_and_attempts.py` | Boolean default `sa.text("0")` → `sa.false()`. The former is SQLite-only; PostgreSQL rejected the migration outright |
| `tests/integration/conftest.py` | Harness variable renamed `TASKCONTROL_TEST_POSTGRES_URL` → `TC_TEST_POSTGRES_URL`, since the `TASKCONTROL_` namespace belongs to validated application settings; reset fixture now derives its table list from model metadata |
| `src/taskcontrol/infrastructure/migrations.py` | Migration failures report the driver's own first line; URLs still never included |

**Known and deliberate gaps**, both recorded rather than fixed silently:

- Four Wave 3 source docstrings still assert the superseded internal-scheduler direction.
  Itemised by file in blueprint R1; not edited in a documentation-only reconciliation.
- `examples/` still demonstrates the data model rather than operational work, so the
  repository currently **fails** the recognition test. Noted for R2.

## R1 — 2026-07-27

| File | Change |
|---|---|
| `reviews/R1_WAVE3_COMPATIBILITY.md` | **New.** Evidence-based review; every claim produced by running the code |
| `10_IMPLEMENTATION_BLUEPRINT.md` | R1 marked complete with its outcome; R2 gains two build items the review proved necessary |
| `00_CONTEXT_INDEX.md` | Status advanced to R2; review indexed |

Source changes, all authorised by the R1 scope: five docstrings corrected;
`ProcessLocalOverlapLock` demoted to a test double with `NoOverlapProtection` wired in its
place; `activation_policy` added to the revision at schema 1.1.

## Summary

| State | Files |
| --- | --- |
| Canonical | 73 |
| Superseded (archived) | 13 |
| Future | 2 |
| Archive index | 1 |
| **Total** | **89** |

Canonical includes the root `README.md`; Future is `future/README.md` and `future/DEFERRED_CAPABILITIES.md`.

Net change from the pre-canonicalization repository: 77 → 89 files. Nothing was deleted. Thirteen documents moved to `archive/` with banners, two new packages were created (`future/`, and the top-level index and blueprint), and four ADRs were added to resolve four standing conflicts.

---

## Level 0 — Identity

| File | State | Reason |
| --- | --- | --- |
| `/README.md` | Canonical | Public product description; updated to state the Phase 1 boundary and point at the context index |
| `product/OPERATIONAL_MODEL_AND_PRODUCT_INTENT.md` | Canonical | **New.** The operational model that inspired the product, supplied by the owner. Historical and conceptual by design, and binding on implementation |
| `product/PRODUCT_DESIGN_VISION.md` | Canonical | **New.** Conceptual design vision from the operations-engineer perspective, supplied by the owner. States that operational work — not scheduling — is the primary domain concept |
| `product/README.md` | Canonical | Product package index; precedence claim replaced by a pointer to the context index |
| `product/PRODUCT_VISION.md` | Canonical | Mission, value, principles. Sole authority for why the product exists |
| `product/PRODUCT_SCOPE.md` | Canonical | Sole authority for in/out of scope and the first-release boundary |
| `product/PRODUCT_PHILOSOPHY.md` | Canonical | Migrated from `vision/03_PRODUCT_PHILOSOPHY.md`. Reconciled with ADR 0018 (two delivery modes, in order) and ADR 0016 (outcome vocabulary removed, now referenced) |
| `product/USERS_AND_USE_CASES.md` | Canonical | Target users and workloads |
| `product/USER_JOURNEYS.md` | Canonical | Migrated from `vision/04_USE_CASES_AND_USER_JOURNEYS.md`. Every journey now carries a phase marker so it stops implying Phase 1 scope |
| `product/ECOSYSTEM_BOUNDARIES.md` | Canonical | The KAE boundary rules. **Canonical, not Future** — this is TaskControl's own integration boundary, which is core product surface |
| `product/INTEGRATION_STRATEGY.md` | Canonical | Public integration surfaces. **Canonical for the same reason** — the contracts are core; only a consumer's internals would be Future |
| `product/PRODUCT_ROADMAP.md` | Canonical | Sole authority for phases. Waves live in the blueprint |

`vision/` no longer exists. Both of its files were migrated into `product/` and the directory was removed, per the rename-and-migrate instruction rather than deletion.

## Future scope

| File | State | Reason |
| --- | --- | --- |
| `future/README.md` | Future | Defines what Future means, how it differs from Archived, and where external-product material would live |
| `future/DEFERRED_CAPABILITIES.md` | Future | Every capability removed from current scope, with its origin document and phase. Created so that resolving documentation conflicts destroyed no plans |

`future/kae/` does not exist. Every current KAE mention is a boundary rule or an integration contract, which the ADR 0017 classification test places in canonical core documentation. Only KAE's own translation logic would go there, and the repository contains none.

## Level 1 — Architecture

| File | State | Reason |
| --- | --- | --- |
| `architecture/ARCHITECTURE_OVERVIEW.md` | Canonical | New. Absorbs `02_ARCHITECTURE.md` and the stack list from `04_TECHNOLOGY_AND_REPOSITORY_STRUCTURE.md`, reconciled with ADRs 0015/0016/0018. Does not restate the directory tree |
| `domain/README.md` | Canonical | Handbook index. Precedence claim replaced by a pointer; the initial-scope list, which predated ADR 0018, now defers to the blueprint |
| `domain/00_*` … `domain/09_*` | Canonical | The domain handbook, unchanged in substance. The strongest material in the repository |
| `decisions/README.md` | Canonical | ADR index. Its private precedence ladder replaced by a pointer to the single ladder |
| `decisions/0000`–`0014` | Canonical | Existing ADRs, unchanged |
| `decisions/0018_INTERNAL_SCHEDULER_BEFORE_ARTEFACT_DEPLOYMENT.md` | **Superseded** | Replaced by ADR 0022. Retained with reasoning intact — Wave 3 was built under it |
| `decisions/0021_PROCESS_LOCAL_OVERLAP_LOCKING.md` | **Superseded** | Replaced by ADR 0023. Its premise (one process) was removed by cron-backed activation |
| `decisions/0022_CRON_BACKED_ACTIVATION.md` | Canonical | **New, R0.** Cron owns recurring activation |
| `decisions/0023_DURABLE_CLAIM_AS_ONE_CAPABILITY.md` | Canonical | **New, R0.** Overlap leases and queue claims are one primitive |
| `decisions/0024_ACTIVATION_POLICY_UNDER_DEGRADED_CONTROL_STATE.md` | Canonical | **New, R0.** Per-task behaviour when persistence is unreachable |
| `realignment/` (9 files) | Historical | Provenance for the correction; excluded from context loading |
| `decisions/0015_CANONICAL_REPOSITORY_LAYOUT.md` | Canonical | **New.** Resolves four rival layouts |
| `decisions/0016_EXECUTION_STATE_AND_OUTCOME_TAXONOMY.md` | Canonical | **New.** Resolves three rival outcome vocabularies; splits lifecycle state from terminal outcome |
| `decisions/0017_DOCUMENTATION_LEVELS_AND_CANONICALIZATION.md` | Canonical | **New.** Documentation levels, five lifecycle states, supersession rule, prohibition on conflict-driven document creation |
| `decisions/0018_INTERNAL_SCHEDULER_BEFORE_ARTEFACT_DEPLOYMENT.md` | Canonical | **New.** Resolves the generation-versus-orchestration thesis conflict by ordering them |
| `decisions/0019_COMPOSITION_ROOTS_INSIDE_THE_PACKAGE.md` | Canonical | **New, Wave 0.** Corrects the `apps/` placement in ADR 0015: a top-level `apps/` is absent from an installed wheel |
| `engineering/README.md` | Canonical | Handbook index; precedence claim replaced by a pointer |
| `engineering/**` (12 files) | Canonical | Charter, laws, structure, dependency rules, standards, quality, governance, AI policy |
| `engineering/repository/10_REPOSITORY_STRUCTURE.md` | Canonical | **Sole authority for the directory tree** per ADR 0015 |
| `engineering/quality/30_TESTING_AND_QUALITY_STRATEGY.md` | Canonical | Gained contract, golden-file, and property/parameterised test requirements merged from `06_ENGINEERING_STANDARDS.md` |

## Level 2 — Blueprint

| File | State | Reason |
| --- | --- | --- |
| `10_IMPLEMENTATION_BLUEPRINT.md` | Canonical | **New.** The construction manual and the only answer to "what do we build next". Phase 1 as Waves 0–10 with file-level outputs, acceptance criteria, and gates |

## Level 3 — Specifications

| File | State | Reason |
| --- | --- | --- |
| `prompts/IMPLEMENTATION_PROMPT.md` | Canonical | **New.** The single prompt. Carries no scope; directs the agent to the index and the current wave |
| `ai-operations/README.md` … `11_*` | Canonical | Twelve agent playbooks, unchanged in substance |

## Entry point and supporting

| File | State | Reason |
| --- | --- | --- |
| `00_CONTEXT_INDEX.md` | Canonical | **New.** The only entry point. File map, levels, precedence ladder, single-authority map, current status |
| `OPEN_QUESTIONS.md` | Canonical | **New.** Four unresolved decisions: licence, persistent-process requirement, approvals in Phase 1, dependency-model boundary |
| `DOCUMENTATION_AUDIT.md` | Canonical | This file |
| `archive/README.md` | Archive index | Lists every archived document and its successor |

## Superseded — archived

All thirteen carry a `STATUS: SUPERSEDED` banner naming the successor and the reason. None was deleted.

| File | Superseded by | Reason |
| --- | --- | --- |
| `archive/OLD_DEVELOPMENT_README.md` | `00_CONTEXT_INDEX.md` | Reading order led through superseded documents first; omitted 14 files |
| `archive/00_PRODUCT_VISION.md` | `product/PRODUCT_VISION.md`, `product/PRODUCT_PHILOSOPHY.md` | Cron-centric framing replaced by standalone positioning. Generation thesis preserved in `future/` and ADR 0018 |
| `archive/01_SCOPE_AND_OPERATING_LEVELS.md` | `product/PRODUCT_SCOPE.md`, `product/PRODUCT_ROADMAP.md` | One of three competing delivery partitions. Levels 2–5 capability lists preserved in `future/` |
| `archive/02_ARCHITECTURE.md` | `architecture/ARCHITECTURE_OVERVIEW.md` | Merged forward and reconciled with ADRs 0015/0016/0018 |
| `archive/03_DOMAIN_MODEL.md` | `domain/`, ADR 0016 | Superseded by the eleven-file handbook; its outcome list was one of three incompatible versions |
| `archive/04_TECHNOLOGY_AND_REPOSITORY_STRUCTURE.md` | ADR 0015, `engineering/repository/10_*` | One of four competing layouts |
| `archive/05_DELIVERY_ROADMAP.md` | `product/PRODUCT_ROADMAP.md`, `10_IMPLEMENTATION_BLUEPRINT.md` | One of three competing partitions. Waves 4–10 content preserved in `future/` |
| `archive/06_ENGINEERING_STANDARDS.md` | `engineering/` | Fully absorbed; unique test requirements merged into `quality/30` |
| `archive/06_FULL_APPLICATION_BLUEPRINT.md` | `10_IMPLEMENTATION_BLUEPRINT.md` | Predated the PR #7 repositioning; built around cron deployment in the first release |
| `archive/00_MASTER_IMPLEMENTATION_PROMPT.md` | `prompts/IMPLEMENTATION_PROMPT.md` | One of three prompts with contradictory scope |
| `archive/01_FULL_APPLICATION_GENERATION_PROMPT.md` | `prompts/IMPLEMENTATION_PROMPT.md` | Instructed building the whole application in one pass; contained a third outcome vocabulary |
| `archive/02_FULL_APPLICATION_ACCEPTANCE_CHECKLIST.md` | per-wave gates in the blueprint | A 167-item whole-application checklist, unmeetable incrementally |
| `archive/03_DOMAIN_IMPLEMENTATION_PROMPT.md` | `prompts/IMPLEMENTATION_PROMPT.md`, blueprint Wave 1 | Domain scope is now a wave, not a prompt |

## Conflicts resolved

| Conflict | Before | After |
| --- | --- | --- |
| Repository layout | 4 rival trees | ADR 0015; one normative statement in `engineering/repository/10_*` |
| Execution outcomes | 3 rival vocabularies, mixed casing | ADR 0016; two enums, one wire format |
| Delivery partition | Operating levels + waves + phases | Phases (Level 0) → waves (Level 2) |
| Prompts | 3 contradictory | 1, carrying no scope |
| Product thesis | Generation vs orchestration, unreconciled | ADR 0018; ordered, both preserved |
| Vision material | `vision/` + `product/` duplicated | Merged into `product/` |
| Precedence | 5 packages each self-declared authoritative | One ladder, in the context index |
| Reading order | Led through superseded documents | One order, in the context index |

## Verification

A reviewer can confirm the result by checking that no non-archived file outside its sole authority contains a repository-tree fence, an execution-outcome enumeration, a repository-wide reading order, or a precedence ladder.
