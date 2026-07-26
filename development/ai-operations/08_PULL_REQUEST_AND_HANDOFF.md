# Pull Request and Handoff Playbook

- Document level: **3 — Specifications**
- Lifecycle state: Canonical

## Objective

Present changes so another engineer can understand the intent, inspect the risk, reproduce verification, and continue the work without hidden context.

## Pull request structure

### Summary

Explain the user or operator outcome and why the change is needed.

### Scope

List the included behaviours and explicit non-goals.

### Design

Describe affected domains, application use cases, adapters, data changes, and applicable ADRs. Highlight intentional trade-offs.

### Changes

Summarise coherent groups of modified files. Avoid a file-by-file transcript when a behavioural explanation is clearer.

### Verification

List exact commands and results. Include migration, integration, manual, and failure-path checks where applicable. Mark tests not run and explain why.

### Security and operations

Describe permissions, secrets, audit, logging, metrics, timeout, retry, deployment, and recovery effects.

### Documentation

Name updated documents or justify why no documentation changed.

### Risks and follow-up

State remaining risks, known limitations, deferred work, and recommended next action.

## Commit guidance

- Each commit should be coherent and build towards the stated outcome.
- Commit messages should explain intent, not merely list files.
- Do not use misleading "fix" language for incomplete or speculative changes.
- Avoid mixing formatting, generated churn, unrelated refactors, and behaviour in one commit.

## Handoff record

When an AI agent stops before completion, it must provide:

- completed work and current branch state;
- files and modules affected;
- decisions and assumptions made;
- commands run and results;
- unresolved errors or blocked dependencies;
- exact next steps;
- actions that must not be repeated or overwritten.

A handoff is not a promise of background work. It is durable context enabling the next human or agent to continue immediately.
