# Ecosystem Boundaries

- Document level: **0 — Identity**
- Lifecycle state: Canonical

## Independent product model

TaskControl is an independently installable and usable application. It may participate in larger platforms, but it is not a subsystem owned by any one of them.

```text
Scripts / People / CI-CD / Business Apps / KAE / Other Systems
                         |
             Public TaskControl interfaces
                         |
                    TaskControl
                         |
       Scheduler / Execution / Persistence / Audit
```

## Relationship to KAE

KAE is a possible consumer of TaskControl.

KAE may:

- submit task definitions or execution requests;
- monitor progress and retrieve results;
- react to events and outcomes;
- correlate execution records with knowledge or project context.

TaskControl must not:

- import KAE domain modules into its core;
- require KAE memory or services to operate;
- expose privileged KAE-only execution semantics;
- shape its general domain model around KAE terminology;
- treat KAE-generated work differently from equivalent work submitted by another client.

## Boundary rule

A capability belongs in TaskControl Core only when it is generally useful for defining, scheduling, executing, observing, or governing automated work.

A capability belongs in an integration when it translates an external system's concepts into TaskControl's public contracts.

A capability belongs outside TaskControl when it performs domain reasoning, knowledge acquisition, content generation, or application-specific business logic.

## Examples

- Retry policy: core capability.
- KAE project-to-task translation: KAE integration.
- GitHub workflow trigger adapter: integration.
- Requirements interview: external application capability.
- Command execution attempt history: core capability.
- Semantic memory of why code was designed: external knowledge service.

## Architectural enforcement

Dependencies point inward toward TaskControl domain and application contracts. External products depend on TaskControl interfaces; TaskControl Core does not depend on external products.
