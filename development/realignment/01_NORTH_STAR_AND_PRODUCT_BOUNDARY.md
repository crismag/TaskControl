# North Star and Product Boundary

- Status: Proposed
- Intended level after reconciliation: Level 0 — Product identity

## North star

> **TaskControl is a cron-backed operational task management and asynchronous orchestration platform. It lets people and remote systems define, submit, govern, observe, and maintain operational work without requiring users to understand cron or operate a replacement scheduler.**

## The problem TaskControl solves

Operational automation is often scattered across crontabs, shell scripts, ad hoc web services, JSON drop folders, databases, and undocumented server conventions. The commands may keep running for years, but teams lose the knowledge and controls surrounding them:

- why a task exists;
- who owns it;
- where its runnable lives;
- which systems carry it;
- how it is scheduled;
- whether the installed schedule matches the intended definition;
- what submitted asynchronous work is waiting, running, complete, or failed;
- whether a failure was retried or requires intervention;
- what changed and who changed it.

TaskControl makes operational work explicit, manageable, remotely accessible, and auditable while retaining cron as the dependable system scheduler.

## Product pillars

### 1. Cron-backed task management

Users describe schedules in ordinary forms such as “daily at 2:00 AM” or through validated advanced expressions. TaskControl translates those definitions into managed cron artefacts and keeps intended and installed state aligned.

### 2. Drop-in runnable management

A user may install a runnable and its task metadata into an approved drop-in directory. TaskControl discovers, validates, registers, and exposes the task without requiring direct crontab editing.

### 3. Operational knowledge

Every task carries purpose, owner, source, schedule, execution target, criticality, runbook, inputs, outputs, dependencies, review status, and lifecycle evidence.

### 4. Remote operations API

Other systems can create or modify managed jobs, inspect status, and submit asynchronous work through stable authenticated contracts rather than SSH, filesystem manipulation, or crontab editing.

### 5. Cron-woken asynchronous queue

Remote callers may submit work items to durable storage. Cron periodically invokes short-lived workers that claim and process queued work, update status, retry safely, and optionally release a next step.

### 6. Optional execution services

TaskControl may wrap or assist execution to provide locking, timeout, logs, evidence, retries, and outcome classification. These services support management and observability; they do not replace cron as the recurring scheduler.

## Explicit non-goals

TaskControl is not primarily:

- a cron replacement;
- a permanently running custom scheduler;
- a generic DAG engine competing with Airflow, Temporal, Prefect, or LangGraph;
- a message broker competing with Kafka or RabbitMQ;
- a container orchestrator;
- a CI/CD platform;
- an AI-agent framework.

Those systems may integrate with TaskControl or inspire adapters, but they do not define its product identity.

## Responsibility boundary

### TaskControl owns

- desired task definitions;
- human-friendly schedule authoring;
- cron artefact generation and lifecycle;
- drop-in discovery and validation;
- task inventory and operational knowledge;
- remote API contracts;
- persistent queued work-item state;
- managed execution metadata and optional runtime helpers;
- drift, audit, and governance.

### Cron owns

- durable time-based activation;
- invoking the installed command or worker according to system scheduling semantics;
- continuing to wake jobs when the TaskControl API or web UI is unavailable.

### The runnable owns

- domain-specific work;
- its external side effects;
- correct idempotency where repeated execution is possible;
- domain-specific validation not delegated to TaskControl.

## Product test

A proposed capability belongs in the core product when it materially improves at least one of these outcomes:

1. ordinary users can manage scheduled work without understanding cron;
2. operators gain reliable knowledge and control over operational tasks;
3. remote systems can safely submit and inspect asynchronous work;
4. cron-backed work remains dependable without a persistent TaskControl scheduler;
5. task state, ownership, changes, and outcomes become auditable.

A capability that only makes TaskControl resemble a generic workflow engine must be rejected, deferred, or isolated behind an adapter unless it passes this test.
