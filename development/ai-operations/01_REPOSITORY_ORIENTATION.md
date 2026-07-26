# Repository Orientation Playbook

- Document level: **3 — Specifications**
- Lifecycle state: Canonical

## Objective

Build enough verified context to modify TaskControl safely without reading the repository as an undifferentiated collection of files.

## Procedure

### 1. Identify the request

Restate the requested outcome, affected user or operator, expected behaviour, and explicit constraints. Separate requested behaviour from inferred implementation.

### 2. Locate authoritative knowledge

Find the relevant vision, roadmap, domain, architecture, engineering, ADR, and prior implementation documents. Prefer accepted repository knowledge over assumptions from general software practice.

### 3. Map affected boundaries

Identify:

- bounded contexts and aggregates;
- application use cases;
- ports and adapters;
- API, CLI, UI, persistence, scheduler, execution, deployment, and plugin surfaces;
- security, audit, configuration, and observability implications.

### 4. Inspect existing implementation

Read entry points, interfaces, domain types, persistence mappings, tests, fixtures, configuration, and migration history connected to the change. Search for similar behaviour before adding new abstractions.

### 5. Establish repository state

Record the active branch, relevant recent changes, existing failures, and whether generated artefacts or migrations are current. Do not attribute pre-existing failures to the proposed change.

## Orientation output

Produce a short context note containing:

- requested outcome;
- authoritative documents consulted;
- affected modules and boundaries;
- applicable ADRs and invariants;
- similar existing patterns;
- uncertainties and risks;
- initial scope and non-goals.

## Stop conditions

Do not implement when:

- two accepted sources materially conflict;
- the requested behaviour violates a domain invariant;
- a destructive or security-sensitive action lacks required policy;
- success criteria cannot be stated;
- the task depends on unavailable external facts or credentials.

Record the conflict or missing decision precisely. Minor gaps may use explicit, reversible assumptions; material gaps require escalation.
