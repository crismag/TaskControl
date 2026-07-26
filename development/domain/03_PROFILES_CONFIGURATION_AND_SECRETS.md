# Profiles, Configuration Resolution, and Secrets

## Purpose

TaskControl must allow operational configuration to be reused across tasks, users, applications, environments, targets, and organisations without embedding mutable values in commands or exposing secrets.

The configuration system must answer two questions reliably:

1. What value will the task receive?
2. Where did that value come from?

## Profile

A Profile is a named, versioned collection of configuration bindings.

Examples:

- Local development defaults.
- Production application environment.
- Exchange-specific runtime values.
- User-specific command paths.
- Host-group deployment settings.

### Attributes

- `profile_id`.
- Name and description.
- Scope type and scope identifier.
- Version.
- Lifecycle state.
- Parent profile references, when enabled.
- Non-secret variable definitions.
- Secret references.
- Labels.
- Created, updated, and published metadata.
- Canonical digest.

### Profile lifecycle

- Draft.
- Published.
- Superseded.
- Disabled.
- Archived.

Published profile versions are immutable. Tasks should bind to an explicit profile version or to a controlled moving reference such as `latest published`, depending on deployment policy.

## Configuration binding

A binding connects a TaskRevision, collection, environment, target, user, or other scope to a Profile.

A binding must specify:

- Source profile and version selection.
- Destination scope.
- Priority or precedence layer.
- Optional condition.
- Whether override is allowed.
- Effective date range.

Bindings are explicit. Merely placing a profile in a folder must not change runtime behaviour.

## Configuration layers

Recommended precedence from lowest to highest:

1. Product defaults.
2. Organisation or tenant defaults.
3. Region defaults.
4. Environment defaults.
5. Application or collection defaults.
6. Target-group defaults.
7. Target-specific profile.
8. TaskRevision profile.
9. Trigger parameters.
10. Authorised one-time execution override.

The exact set may be smaller in the local-first application, but the resolver must model ordered layers.

## Resolution result

Configuration resolution produces:

- Resolved non-secret values.
- Secret references to be materialised at execution boundary.
- Source trace for every key.
- Warnings and conflicts.
- Resolution digest.
- Versions of all profiles used.

### Resolution trace example

```yaml
key: REPORT_DIR
resolved_value: /srv/reports
source:
  layer: environment
  profile_id: prod-reporting
  profile_version: 4
overridden_sources:
  - layer: product_default
    value: /tmp/reports
```

Sensitive values must show only metadata such as provider, reference, and version; never the value.

## VariableDefinition

A non-secret variable definition includes:

- Name.
- Type.
- Value or value template.
- Description.
- Required flag.
- Default policy.
- Validation constraints.
- Export mode.
- Sensitivity classification.

### Supported initial types

- String.
- Integer.
- Number.
- Boolean.
- Path.
- Enum.
- Duration.
- JSON-compatible object.

### Export modes

- Environment variable.
- Command argument.
- Template context only.
- Generated configuration file.
- Plugin-specific channel.

The same resolved value may be exported through more than one explicit binding.

## Template values

Templates may reference safe structured context:

- Task metadata.
- Trigger metadata.
- Target metadata.
- Calendar-derived business date.
- Other previously resolved non-secret keys.

Templates must not execute arbitrary Python or shell code.

Template resolution must:

- Detect cycles.
- Validate missing references.
- Preserve typing where possible.
- Produce a trace.
- Redact secret-derived output.

## SecretReference

A SecretReference identifies a secret managed outside ordinary configuration storage.

### Attributes

- `secret_reference_id`.
- Provider type.
- Provider-specific path or key identifier.
- Optional version or stage.
- Intended usage.
- Scope restrictions.
- Rotation metadata.
- Last validation metadata.

### Initial provider options

- Environment-backed provider for development.
- Local encrypted store, if implemented safely.
- File descriptor or mounted file reference.
- Plugin-defined provider.

Future providers may include HashiCorp Vault, AWS Secrets Manager, Azure Key Vault, Google Secret Manager, or enterprise credential systems.

### Non-negotiable rules

- Secret values are never stored in TaskRevision payloads.
- Secret values are never returned by ordinary API responses.
- Secret values are never written to audit events.
- Secret values are never included in configuration digests.
- Secret values are materialised as late as possible.
- Logs must redact exact values and known encodings where feasible.
- UI fields must distinguish secret references from plaintext values.

## Secret materialisation

Secret materialisation happens at an execution or deployment adapter boundary using the executing principal and target context.

The result should be short-lived and scoped to the current operation.

Materialisation failure must produce a classified pre-execution failure. It must not be reported as a command exit failure because the command never started.

## Conflict handling

Conflicts occur when multiple equally ranked sources define the same key.

Default behaviour:

- Treat ambiguous equal-precedence definitions as an error.
- Permit explicit merge strategies only for compatible structured types.
- Record all conflict sources in the explanation.

Supported merge strategies may eventually include replace, deep merge, append, unique append, and deny override.

## Required-value validation

Before deployment or execution, resolution must validate:

- Required keys exist.
- Values match declared types.
- Paths follow platform rules.
- Enums are valid.
- Secret references are syntactically valid and accessible when validation permissions permit.
- Templates are resolvable.
- No prohibited plaintext secret pattern is present.

## Environment concept

An Environment is an operational scope such as development, test, staging, or production. It is not merely an environment-variable dictionary.

An Environment may define:

- Name and classification.
- Risk level.
- Default profiles.
- Allowed targets.
- Approval policy.
- Secret provider policy.
- Deployment restrictions.
- Retention and audit policy.

The local-first application may ship with one default environment but should preserve the identifier boundary.

## Runtime switches

A RuntimeSwitch is a mutable operational gate suitable for enable/disable behaviour without publishing a new TaskRevision.

Examples:

- Globally disable end-of-day tasks.
- Pause exchange-specific jobs.
- Prevent execution during incident response.

Runtime switches must have:

- Scope.
- Boolean or enum state.
- Reason.
- Expiry, optional.
- Actor and timestamp.
- Audit history.

They should be consumed through RunConditions, not hidden ad hoc checks.

## Persistence guidance

Store profile definitions and versions separately. Store secret references, never secret values. Store resolution traces or reproducible references with executions and deployment plans.

Large resolved configuration snapshots may be stored as redacted JSON plus digests.

## API guidance

Recommended resources:

- `/profiles`
- `/profiles/{profile_id}/versions`
- `/configuration/resolve`
- `/secret-references`
- `/runtime-switches`
- `/environments`

Resolution endpoints must enforce permission checks and redaction.

## CLI guidance

```text
taskctl profile create
taskctl profile publish <profile>
taskctl config resolve <task> --target local --explain
taskctl secret-ref create --provider env --key REPORT_TOKEN
taskctl switch set exchange-x.enabled false --reason "incident"
```

## UI guidance

The UI should provide:

- Profile version history.
- Layered resolution view.
- Origin badge for every effective value.
- Conflict and missing-value warnings.
- Secret-reference selector that never reveals values.
- Runtime-switch dashboard with expiry and reason.

## Audit requirements

Audit:

- Profile creation, edit, publication, disablement, and archive.
- Binding changes.
- Runtime-switch changes.
- Secret-reference metadata changes.
- Access validation attempts where policy requires.
- One-time runtime overrides.

Do not audit secret values.

## Future extensions

- Configuration promotion between environments.
- Signed profile bundles.
- Dynamic external configuration providers.
- Secret lease renewal.
- Per-key access control.
- Organisational policy constraints.
- Configuration drift comparison against target runtime state.