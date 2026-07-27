# Wave 3 Reuse and Misalignments

- Status: Proposed assessment
- Baseline: Wave 3 merged in PR #13

## Conclusion

Wave 3 should be retained. It provides valuable execution services, but it must be repositioned from the centre of the product to a supporting layer invoked by cron-backed workflows, queue workers, and explicit administrative operations.

## Reusable capabilities

The following remain valuable:

- executor ports and command adapters;
- process launch and termination handling;
- output capture and secret redaction;
- timeout and cancellation policy;
- attempt persistence;
- retry classification;
- execution outcome vocabulary;
- process-local locking as an initial single-host protection;
- stable application services for one bounded execution;
- tests covering success, failure, timeout, launch error, and terminal persistence.

These capabilities can support:

1. a cron-invoked wrapper for one recurring task;
2. a queue worker processing one claimed item;
3. an explicit run-now administrative request;
4. validation and diagnostic execution before deployment.

## Misaligned assumptions to remove

The following assumptions must not govern future work:

- TaskControl must own an internal recurring scheduler in Phase 1.
- TaskControl must remain alive to activate scheduled work.
- `taskctl execute <task>` is the primary user experience.
- crontab generation and management are merely deferred deployment features.
- cron is a legacy format to be replaced after execution semantics are proven.
- dependencies necessarily imply a generic workflow engine.
- every remote orchestration request should synchronously launch work.

## Required code review before reuse

The product-realignment PR should not rewrite Wave 3 code without evidence. It should create a follow-up technical review that checks:

- whether execution services are callable from short-lived cron processes;
- whether they assume one persistent in-memory scheduler;
- whether persistence and locking work across independent process invocations;
- whether attempts can be associated with scheduled activations and queued work items;
- whether failure to reach optional control-plane services blocks local execution;
- whether configuration can be resolved entirely from locally deployed assets where required;
- whether process-local locking is sufficient for the first cron-backed slice;
- which names encode the old scheduler-first product model.

## Domain concepts likely to survive

- Task and immutable task revision
- Action or execution specification
- Execution and attempt
- Outcome and reason code
- Retry and timeout policy
- Schedule value objects
- Configuration resolution
- Idempotency key
- Correlation identifier

## Domain concepts requiring reinterpretation

### Schedule

A schedule is desired activation intent rendered and deployed through a scheduler adapter. It is not proof that an internal scheduler must exist.

### Execution

An execution is one managed attempt to perform work. It may be initiated by cron, a queue worker, or a deliberate run-now command.

### Dependency

Initial dependencies should support operational eligibility and constrained next-step release. They should not automatically grow into a universal DAG language.

### Runtime

Runtime means bounded execution services. It does not mean an always-on scheduler daemon.

## Preserve history honestly

Do not rewrite Wave 3 documentation as though it had always targeted the new architecture. Record that it was implemented under the previous internal-scheduler direction, then explain which parts are retained, repurposed, or superseded.

## Recommended transition status

- Waves 0–3: **complete under previous direction; retained pending compatibility review**.
- Wave 4 from the old blueprint: **cancelled or paused pending supersession**.
- Next work: **Product Realignment Wave R0 — canonical documentation and ADR reconciliation**.
- First implementation after R0: **Cron-backed managed task vertical slice**, not the old expectations wave by default.
