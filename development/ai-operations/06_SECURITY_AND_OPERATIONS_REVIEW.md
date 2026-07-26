# Security and Operations Review Playbook

- Document level: **3 — Specifications**
- Lifecycle state: Canonical

## Objective

Ensure a change can be operated safely, diagnosed under failure, and trusted with production data and credentials.

## Security review

Assess:

- authentication and authorisation boundaries;
- least-privilege permissions for users, agents, plugins, and executors;
- validation of untrusted input and command arguments;
- injection, path traversal, unsafe deserialisation, and code-execution risks;
- secret acquisition, storage, redaction, rotation, and non-persistence;
- tenant or ownership isolation where applicable;
- audit coverage for privileged and destructive actions;
- sensitive data in logs, traces, errors, artefacts, and API responses;
- dependency and supply-chain impact.

AI agents must not insert real credentials, weaken controls for local convenience, or introduce unaudited privileged bypasses.

## Operations review

Assess:

- structured logs with correlation identifiers;
- metrics for throughput, latency, success, failure, retries, queueing, and resource use;
- traces across meaningful boundaries;
- health and readiness behaviour;
- timeout, cancellation, retry, and backoff policy;
- idempotency and duplicate-delivery handling;
- resource limits and cleanup;
- operator-visible errors and remediation guidance;
- deployment, rollback, recovery, and drift implications;
- configuration defaults and provenance.

## Failure exercise

For operationally meaningful changes, describe what happens when:

1. the database is unavailable;
2. an external adapter times out;
3. a process exits but business success criteria fail;
4. an operation is retried after partial completion;
5. the service restarts during work;
6. logs or audit storage are temporarily unavailable;
7. a configuration source conflicts with another source.

## Review output

Record security findings, operational dependencies, dashboards or signals required, recovery steps, and any production readiness work intentionally deferred.
