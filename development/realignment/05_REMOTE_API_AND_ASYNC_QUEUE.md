# Remote API and Asynchronous Queue

- Status: Proposed

## Purpose

TaskControl should let remote applications submit operational work without knowing the target host, cron configuration, runnable path, or execution implementation.

This capability extends the existing API direction into a deliberate asynchronous service model.

## Core interaction

```text
Remote client
    |
    | POST work item
    v
TaskControl API
    |
    | durable write
    v
Work-item store
    |
    | cron periodically invokes worker
    v
Bounded queue worker
    |
    | claim, execute, update, retry, release next step
    v
Status and audit history
```

The API acknowledges durable acceptance, not immediate completion.

## Work-item contract

A work item should initially contain:

- unique identifier;
- registered task type or handler identifier;
- payload validated against an approved schema;
- idempotency key;
- submission source and correlation identifier;
- creation time;
- optional not-before time;
- bounded priority;
- current state;
- attempt count and retry policy reference;
- result or error reference;
- optional parent, child, or explicit next-step relation.

## Suggested state model

```text
RECEIVED
  -> READY
  -> CLAIMED
  -> RUNNING
  -> SUCCEEDED
  -> FAILED
  -> RETRY_WAIT
  -> CANCELLED
  -> DEAD_LETTER
```

The exact taxonomy should reuse or carefully map to the existing execution-domain vocabulary rather than create competing names.

## Claiming requirements

Queue claiming must be safe across overlapping cron invocations.

The design must specify:

- atomic claim semantics;
- lease or claim expiry;
- recovery after worker death;
- maximum batch size and execution duration;
- ordering guarantees, if any;
- idempotency behaviour;
- duplicate submission behaviour;
- retry delay and terminal failure handling.

SQLite may support a single-host initial version. PostgreSQL should remain available for stronger concurrency and multi-process use. JSON files may be supported only as an explicit low-concurrency adapter, not as the correctness baseline.

## Registered handlers, not arbitrary commands

Ordinary API clients submit work against a pre-registered task type or approved template. They must not provide unrestricted shell commands.

Separate privileges should exist for:

- submit work;
- inspect work;
- cancel work;
- create or revise task definitions;
- deploy cron artefacts;
- administer secrets and hosts.

## Pipeline accumulation

Initial pipeline support should remain deliberately constrained:

- a successful item may enqueue a known next task;
- a parent may wait for a bounded set of children;
- failure policy may stop, retry, or route to a failure handler;
- all transitions are durable and auditable.

Do not introduce a generic graph DSL in the first implementation. Complex DAGs and agent loops are future capabilities requiring separate validation.

## API surface direction

Representative endpoints may include:

```http
POST   /api/v1/work-items
GET    /api/v1/work-items/{id}
GET    /api/v1/work-items
POST   /api/v1/work-items/{id}/cancel
POST   /api/v1/work-items/{id}/retry

GET    /api/v1/task-types
POST   /api/v1/tasks
PATCH  /api/v1/tasks/{id}
POST   /api/v1/tasks/{id}/deploy
GET    /api/v1/tasks/{id}/drift
```

These are directional examples, not frozen contracts.

## Cron relationship

Cron does not create each remotely submitted work item. Cron activates one or more stable queue-worker entries. The worker processes eligible durable items and exits after a bounded amount of work.

This preserves the intended model:

- remote systems throw tasks into the queue;
- TaskControl stores and governs them;
- cron provides reliable recurring wake-up;
- short-lived workers process accumulated work;
- clients inspect status asynchronously.

## Product boundary

The queue should solve dependable operational request processing, not broker-scale messaging. Throughput, latency, fan-out, streaming, and cross-region guarantees must remain modest until demonstrated demand justifies a specialised subsystem or external broker adapter.
