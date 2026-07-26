# ADR 0013: React and TypeScript for the Web Interface

- Status: Accepted
- Date: 2026-07-26

## Context

TaskControl needs an interactive web interface for definitions, schedules, execution history, deployment plans, approvals, configuration explanations, and operational status.

## Decision

Use React with TypeScript for the initial web application. The frontend consumes versioned API contracts and does not directly encode authoritative domain rules.

## Rationale

React and TypeScript provide a mature component ecosystem, strong tooling, typed client contracts, and broad maintainability for an operations-oriented interface.

## Consequences

The project operates separate Python and Node-based build toolchains. Domain validation must still occur server-side, even when duplicated for responsive user feedback.

## Constraints

- Generated or shared API types are preferred over handwritten drift-prone contracts.
- Client state distinguishes server authority from local draft state.
- Accessibility, loading, empty, error, and partial-data states are part of completion.
- Sensitive values and authorisation decisions never rely on client enforcement.
- UI components do not access persistence or infrastructure directly.

## Review triggers

A framework replacement requires evidence based on maintainability, capability, or operational need—not trend preference.
