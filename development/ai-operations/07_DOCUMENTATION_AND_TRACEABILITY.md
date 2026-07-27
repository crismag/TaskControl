# Documentation and Traceability Playbook

- Document level: **3 — Specifications**
- Lifecycle state: Canonical

## Objective

Keep implementation, engineering knowledge, and decision history aligned so future humans and agents do not reconstruct intent from code alone.

## Documentation assessment

For every change, determine whether it affects:

- product behaviour or user journeys;
- domain language, invariants, states, or ownership;
- architecture, dependencies, or integration boundaries;
- an accepted architectural decision;
- API, CLI, UI, event, plugin, or configuration contracts;
- data models and migration expectations;
- deployment, operation, security, or recovery procedures;
- implementation roadmap and remaining work.

Update the owning document rather than duplicating policy in many locations.

## Traceability chain

Material work should be traceable through:

`requirement or issue -> acceptance criteria -> design/ADR -> implementation -> tests -> documentation -> PR evidence`

Links or identifiers should be included where repository tooling supports them.

## Assumption record

Record assumptions that affect behaviour, architecture, data, security, or operations. Each assumption should state:

- why it was needed;
- the evidence supporting it;
- whether it is reversible;
- what would invalidate it;
- where follow-up work is tracked.

Do not turn unresolved material questions into undocumented implementation choices.

## ADR handling

Create a new ADR when a change establishes a durable architecture rule, selects among meaningful alternatives, introduces a difficult-to-reverse dependency, or supersedes an accepted decision. Do not rewrite accepted ADR history to make the current design appear inevitable.

## Documentation quality

Documentation must describe actual behaviour, not aspiration presented as completion. Clearly label planned, proposed, experimental, deprecated, and implemented states. Examples and commands must be safe and plausible.

## Completion statement

The PR should state which documents changed. When none changed, provide a brief justification demonstrating that the assessment was performed.
