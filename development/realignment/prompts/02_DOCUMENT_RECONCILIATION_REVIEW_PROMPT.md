# Prompt — Review the Product Realignment PR

## Role

Act as a critical product, architecture, and documentation-governance reviewer. Review the proposed TaskControl realignment after the implementation agent has updated canonical documents.

## Review objective

Determine whether the repository now communicates one coherent product:

> TaskControl is a cron-backed operational task management and asynchronous orchestration platform. Cron owns recurring activation; TaskControl owns task lifecycle, cron management, operational knowledge, remote submission, durable work-item state, observation, and audit.

## Required checks

### Product identity

- Is cron clearly a dependable backing scheduler rather than a competitor or temporary adapter?
- Can an ordinary user create and manage scheduled work without understanding cron?
- Is operational knowledge a core outcome?
- Is remote asynchronous submission explicit?
- Is the product distinct from a generic workflow engine, AI-agent framework, or message broker?

### Architecture

- Are control plane, cron management, queue, execution services, persistence, and runnables separated?
- Can already-installed scheduled work survive API/UI downtime?
- Are short-lived cron-invoked processes supported?
- Does Wave 3 remain reusable without defining the product identity?
- Are scheduler-management and executor concerns represented through ports and adapters?

### Cron management

- Are plan, apply, verify, import/adopt, enable/disable, and drift concepts present?
- Are unmanaged cron entries protected from accidental overwrite?
- Are managed artefacts deterministic and identifiable?
- Are drop-in packages treated as first-class and safely validated?

### Asynchronous queue

- Does API submission return durable acceptance rather than synchronous execution?
- Are claiming, leases/recovery, retries, idempotency, and terminal states addressed or explicitly deferred?
- Is the first queue intentionally bounded and simpler than a broker?
- Is arbitrary remote shell submission prohibited by default?
- Are pipeline relationships constrained rather than expanded into a generic graph DSL?

### Documentation governance

- Is there exactly one active authority for identity, scope, roadmap, architecture, and next implementation work?
- Was ADR 0018 superseded honestly rather than erased?
- Were all contradictory documents updated or archived?
- Do the context index and documentation audit match reality?
- Is proposal material clearly separated from canonical documentation?

### Roadmap

- Is the previous Wave 4 progression stopped?
- Are Waves 0–3 retained with a compatibility review?
- Does the next vertical slice prove cron-backed user value?
- Does a later bounded slice prove remote queue submission and cron-woken processing?
- Are complex DAGs, remote worker fleets, and broker-scale claims deferred?

## Search terms

Search the repository for at least:

- internal scheduler
- persistent local process
- executes work itself
- scheduling is not automatic
- no Phase 1 code writes
- crontab deferred
- scheduler artefacts
- `taskctl execute`
- workflow engine
- cron replacement
- queue
- drop-in
- drift

Classify each remaining occurrence as canonical, historical, future, code terminology, or contradiction.

## Output format

Provide:

1. verdict: approve, approve with follow-ups, or request changes;
2. blocking contradictions;
3. architecture risks;
4. missing acceptance criteria;
5. documents that still compete for authority;
6. source assumptions that need the next technical review;
7. a concise recommended correction list.

Do not approve merely because the new vision text is attractive. Approve only when active documents, roadmap, and implementation guidance converge.
