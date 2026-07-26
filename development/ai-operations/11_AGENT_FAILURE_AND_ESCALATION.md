# Agent Failure and Escalation Playbook

- Document level: **3 — Specifications**
- Lifecycle state: Canonical

## Objective

Define how an AI engineering agent responds when it cannot complete work safely, accurately, or within its available authority.

## Failure classes

### Context failure

Required files, history, issue details, credentials, environments, or external evidence are unavailable.

### Requirement conflict

Sources disagree, acceptance criteria contradict domain rules, or the requested outcome is materially ambiguous.

### Architecture conflict

The apparent implementation requires violating an accepted ADR or engineering law.

### Verification failure

Tests fail, the environment cannot run required checks, migrations cannot be exercised, or external integration behaviour cannot be confirmed.

### Security or destructive-risk failure

The task could expose secrets, bypass permissions, destroy data, execute unsafe commands, or perform an irreversible production action without adequate controls.

### Capability failure

The agent lacks the tool, repository access, platform, or supported operation needed to perform the requested change.

## Required response

When blocked, the agent must:

1. stop the unsafe or unsupported action;
2. state the exact blocked outcome;
3. identify the failure class and supporting evidence;
4. preserve completed safe work;
5. separate verified facts from hypotheses;
6. propose the smallest concrete resolution;
7. leave a handoff that another engineer can execute.

## Assumption policy

An agent may use an assumption only when it is:

- low risk;
- reversible;
- consistent with accepted repository knowledge;
- clearly documented;
- not security-sensitive or destructive;
- unlikely to alter public behaviour materially.

Material architecture, domain, data retention, permission, compatibility, and product decisions must not be guessed.

## Partial completion

Partial work is acceptable when it remains coherent and does not leave the branch knowingly broken. Clearly distinguish completed, stubbed, unverified, and deferred elements. Do not create fake implementations or placeholder tests that imply completion.

## Escalation record

Use this format:

```text
Blocked outcome:
Failure class:
Evidence:
Safe work completed:
Unverified assumptions:
Required decision or access:
Recommended next action:
Files/commands for continuation:
```

Escalation is an engineering control, not a failure to appear confident.
