# Runtime, Observability, and Security Standards

- Document level: **1 — Architecture**
- Lifecycle state: Canonical

## Execution runtime

The runtime must preserve the domain distinctions between trigger, eligibility decision, execution, attempt, process result, expected-outcome evaluation, and final classification.

- Retries create new attempts under the same execution.
- Timeouts are explicit and layered.
- Cancellation is a state transition, not merely a process signal.
- Duplicate trigger delivery must not create duplicate execution side effects.
- Unknown outcomes remain unknown until reconciled; they are not converted to success.
- Worker crashes and lease expiry require safe recovery rules.

## Structured logging

Production logs should be structured and include relevant correlation fields:

- request or correlation ID;
- task and task-revision ID;
- trigger ID;
- execution and attempt ID;
- deployment and plan ID;
- actor or principal ID where safe;
- adapter and target identifiers.

Use levels consistently:

- `DEBUG`: diagnostic detail disabled in normal production use;
- `INFO`: normal lifecycle milestones;
- `WARNING`: recoverable abnormal conditions or degradation;
- `ERROR`: failed operation requiring attention;
- `CRITICAL`: system integrity or broad availability threat.

Never log secret values, tokens, credentials, private keys, full environment dumps, or unrestricted command output that may contain secrets.

## Metrics

Metrics should describe rates, latency, saturation, failures, retries, queue depth, lock contention, drift, notification delivery, and reconciliation. Avoid high-cardinality labels such as raw execution IDs.

## Tracing

Propagate correlation context across API, application, database, scheduler, worker, and integration boundaries. Trace data must follow the same redaction rules as logs.

## Health endpoints

Separate process liveness from readiness. Readiness should validate only dependencies required to serve the advertised capability and should not perform expensive work.

## Authentication and authorisation

Authentication identifies a principal. Authorisation evaluates permissions and policy for the requested resource and action. Enforce authorisation in application use cases, not only in UI or route decorators.

## Secrets

Persist references, not secret values. Resolve secrets as late as practical at the execution or deployment boundary. Secret providers are adapters. Redact secrets from logs, errors, audit metadata, generated plans, and test fixtures.

## Audit

Security-sensitive and operationally significant actions must produce append-only audit records, including actor, action, resource, decision, timestamp, correlation, and safe before/after references where applicable.

## Input and process safety

Do not construct shell commands through unsafe string interpolation. Prefer argument arrays and explicit environment maps. Validate file paths, target identifiers, plugin input, callback destinations, and generated artefact locations.
