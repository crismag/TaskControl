# ADR 0017: Documentation Levels and Repository Canonicalization

- Document level: **1 — Architecture**
- Lifecycle state: Canonical
- Status: Accepted
- Date: 2026-07-26
- Owners: TaskControl maintainers
- Supersedes: Reading orders in `development/archive/README.md` and package-level precedence claims in `domain/README.md`, `engineering/README.md`, and `product/README.md`
- Superseded by: None
- Related documents: `development/00_CONTEXT_INDEX.md`, `development/10_IMPLEMENTATION_BLUEPRINT.md`, ADR 0015, ADR 0016, ADR 0018

## Context

Between the initial commit and PR #7 the repository accumulated seven documentation packages and 77 files without a single line of code. Each package was added rather than integrated. The result was measurable drift:

- four rival repository layouts (resolved by ADR 0015);
- three rival execution-outcome vocabularies (resolved by ADR 0016);
- three rival delivery partitions — operating levels, delivery waves, product phases;
- three prompts giving contradictory instructions about what to build now;
- duplicate vision material in `vision/` and `product/`;
- five packages each declaring themselves authoritative, with no global precedence rule;
- a stated reading order that walked a reader through superseded documents first.

The root cause is procedural, not editorial. New insight was recorded as an additional document instead of as an edit to the document it invalidated. Documentation forked where it should have evolved. This is architectural drift, reproduced in prose.

A repository must never require a reader to adjudicate between documents. Every architectural question needs exactly one answer, in exactly one place.

## Decision drivers

- Coding agents treat all context as authoritative and cannot resolve contradictions safely.
- Precedence must be global and stated once, not claimed independently by each package.
- Superseded content must stop being readable as current.
- Deferred features must survive canonicalization; removing a contradiction must not silently delete a planned capability.
- The rule must be cheap enough to follow on every future PR.

## Considered options

### Option A — Keep additive packages, add a precedence table

Lowest effort. Leaves stale text in place; readers still encounter superseded documents and must apply the table by hand. Drift continues, merely annotated.

### Option B — Documentation levels with a single entry point and mandatory supersession

Requires a one-time reconciliation pass and discipline on each PR. Produces one answer per question and makes "what does this change supersede?" a required part of every documentation change.

## Decision

Adopt **Option B**.

### Documentation levels

Every document in `development/` declares a level in its front matter. Higher levels govern lower ones. A lower level may refine a higher one; it may never redefine it.

| Level | Name | Answers | Location |
| --- | --- | --- | --- |
| 0 | Identity | Why does TaskControl exist, for whom, and what is out of scope? | `README.md`, `development/product/` |
| 1 | Architecture | What are the boundaries, concepts, decisions, and engineering rules? | `development/architecture/`, `development/domain/`, `development/decisions/`, `development/engineering/` |
| 2 | Blueprint | Given today's repository, what do we build next? | `development/10_IMPLEMENTATION_BLUEPRINT.md` |
| 3 | Specifications | How is one specific wave or capability built and accepted? | `development/specifications/`, `development/ai-operations/`, `development/prompts/` |
| 4 | Source | The implementation itself. | `src/`, `apps/`, `web/`, `tests/` |

Precedence within Level 1: an accepted ADR outranks the domain handbook, which outranks architecture prose, which outranks engineering governance. Product constraints at Level 0 outrank all of it.

### Single entry point

`development/00_CONTEXT_INDEX.md` is the only documented starting point. It carries the file map, the level of each document, the precedence ladder, and the current implementation status. No other document publishes a reading order. Package `README.md` files describe their own contents and defer to the index for precedence.

### The blueprint is the construction manual

`development/10_IMPLEMENTATION_BLUEPRINT.md` is the single Level 2 document and the only place that answers "what do we build next". It is not architecture, not roadmap, and not vision — it is construction. There is exactly one delivery partition in the repository: product phases at Level 0 decompose into blueprint waves at Level 2. Operating levels and delivery waves as previously written are retired; their forward-looking content survives in `future/DEFERRED_CAPABILITIES.md`.

### One prompt

`development/prompts/` contains exactly one prompt. It carries no scope of its own; it directs the agent to the context index and the blueprint's current wave. Scope lives in the blueprint, where it can change without editing a prompt.

### Supersession rule

Every documentation pull request must state, in its description:

1. **Supersedes** — which documents this change invalidates, in whole or in part.
2. **Updates** — how each was edited, merged, or archived.
3. **Deletes** — which duplicates were removed.

A PR that introduces a new package without naming what it supersedes is rejected. Adding a document is the exception; editing the document that was already wrong is the norm.

### Document lifecycle states

No document is deleted merely because it no longer matches the current implementation. Every document in `development/` carries exactly one lifecycle state, declared in its header.

| State | Meaning | Location | Used for implementation? |
| --- | --- | --- | --- |
| **Canonical** | Current source of truth. Governs implementation, referenced by the context index, actively maintained. | in place | yes |
| **Superseded** | Replaced by a named successor. Retains useful historical reasoning. Carries a banner naming its successor. | in place or `archive/` | no |
| **Archived** | Historically important but no longer descriptive of any plan: abandoned architectures, previous product positioning, rejected layouts. | `archive/` | no |
| **Future** | Correct and valuable, but deliberately outside current TaskControl scope. Not obsolete — unscheduled. | `future/` | no |
| **Open decision** | An unresolved choice. Does not remain as prose; becomes an entry in `OPEN_QUESTIONS.md`. | `OPEN_QUESTIONS.md` | no |

A **Superseded** banner reads:

```text
> **STATUS: SUPERSEDED** — replaced by `development/product/PRODUCT_SCOPE.md`.
> Retained for historical reasoning. Do not use for new implementation.
```

A **Future** banner reads:

```text
> **STATUS: FUTURE** — describes planned ecosystem capability intentionally
> outside current TaskControl product scope. Not part of Phase 1 implementation.
```

### Classifying material that names an external product

TaskControl is designed to support external consumers such as KAE through public interfaces. Mentioning an external product is never grounds for reclassification. Apply this test instead:

| Material | State |
| --- | --- |
| TaskControl implementation | Canonical |
| TaskControl extension points, ports, and public contracts that an external product would use | **Canonical** — these are core product surface |
| External-product-specific implementation, translation, or behaviour | Future (`future/<product>/`) |
| Designs contradicted or replaced by a later decision | Superseded or Archived |

The integration boundary belongs in core documentation. The integrating product's internal logic does not.

### Prohibition on conflict-driven document creation

Discovering a conflict is **not** a reason to write a new document. On encountering conflicting documentation:

1. Determine which document should remain authoritative.
2. Migrate any unique information into that document.
3. Update cross-references repository-wide.
4. Classify the replaced document as Superseded, Archived, or Future and apply its banner.
5. Leave no competing authoritative documents.

Do not create another product-definition document unless explicitly instructed to. This ADR exists because the opposite behaviour — recording each new insight as an additional package — produced the drift being corrected here.

### Reconciliation reporting

A canonicalization or reconciliation pull request produces `development/DOCUMENTATION_AUDIT.md`: every file, its lifecycle state, and the reason. It is updated whenever a document changes state, and is the inventory a maintainer reads to understand why each file exists.

## Rationale

The levels give every future change a home and a test. A proposed edit that changes why the product exists is Level 0 and forces Level 1 and 2 review. A proposed edit that changes what to build next is Level 2 and must not silently alter Level 0. The supersession rule converts the failure mode observed across PRs #5–#7 into a checklist item that costs a sentence.

## Consequences

### Positive

- One answer per architectural question.
- Agents load a bounded, current context from one entry point.
- Documentation drift becomes visible at review time.

### Negative or accepted trade-offs

- A one-time reconciliation pass touching most of the repository.
- Every documentation PR carries a small supersession-analysis overhead.
- `development/archive/` retains text that is deliberately not maintained.

### Risks and mitigations

- Risk: an agent reads `development/archive/` anyway — mitigation: archive header states non-authoritative status on line one; the context index excludes it explicitly.
- Risk: the blueprint becomes stale as code lands — mitigation: updating it is an exit criterion of every wave.
- Risk: levels become bureaucracy — mitigation: the level is one line of front matter, not a process.

## Implementation constraints

- Every `development/**/*.md` file outside `archive/` begins with a level declaration.
- No document outside `00_CONTEXT_INDEX.md` publishes a reading order.
- No document outside `10_IMPLEMENTATION_BLUEPRINT.md` states what is built next.
- No document outside `engineering/repository/10_REPOSITORY_STRUCTURE.md` states the directory tree.
- No document outside ADR 0016 enumerates execution states or outcomes.

## Validation

A reviewer can verify by grepping for duplicate authority: a repository-tree fence, a reading-order heading, or an outcome enumeration appearing in more than one non-archived file is a defect.

## Migration and compatibility

Performed in the canonicalization pull request that introduces this ADR. No code is affected.

## Future evolution and review triggers

Reconsider when Level 3 specifications become numerous enough to need their own index, or when the repository is split into multiple distributions.

## Rejected alternatives

Option A was rejected because annotating contradictions does not remove them, and the observed failure mode is that readers and agents encounter stale text before they encounter the annotation.
