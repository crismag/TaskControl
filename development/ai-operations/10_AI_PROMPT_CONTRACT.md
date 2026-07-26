# AI Prompt Contract

## Objective

Define the minimum information and behavioural constraints for task-specific prompts issued to AI engineering agents.

## Required prompt sections

### Role

Name the engineering responsibility required, such as domain implementation, API integration, migration review, security assessment, or release preparation. Avoid vague claims of unlimited expertise.

### Outcome

Describe the observable result, affected actor, and reason for the work.

### Authoritative context

List repository documents, issues, ADRs, existing modules, and tests that must govern the task. The agent must inspect them rather than rely on excerpts alone when repository access exists.

### Scope and non-goals

State included behaviours, excluded work, compatibility requirements, and constraints on refactoring or dependencies.

### Acceptance criteria

Use verifiable statements covering success, rejection, failure, security, audit, and operations where material.

### Required process

Require orientation, a plan, incremental implementation, tests, structured self-review, documentation assessment, and PR-ready handoff.

### Evidence

Require changed-file summary, commands run, results, assumptions, risks, and unfinished work.

## Standard agent instructions

A TaskControl engineering prompt should include these rules:

- Follow accepted domain, engineering, and ADR documents.
- Do not invent material requirements.
- Keep dependencies pointing inward.
- Keep business logic outside delivery, persistence, UI, and integration adapters.
- Make configuration and important decisions explainable.
- Test material success and failure paths.
- Do not claim verification that was not performed.
- Update documentation or justify why none changed.
- Stop and report a conflict rather than silently violating policy.

## Prompt anti-patterns

Avoid prompts that:

- ask an agent to "build the whole application" in one change;
- specify filenames without describing behaviour;
- demand speed at the expense of tests or architecture;
- paste large context while omitting its authority or status;
- mix research, design approval, implementation, and production rollout without gates;
- instruct the agent to make all decisions autonomously;
- omit non-goals and completion evidence.

## Reusable task template

```text
Role:
Outcome:
Authoritative context:
Current behaviour:
Scope:
Non-goals:
Acceptance criteria:
Constraints and applicable ADRs:
Required tests and verification:
Documentation requirements:
Expected PR/handoff output:
```

A prompt is an execution contract, not a substitute for repository knowledge.