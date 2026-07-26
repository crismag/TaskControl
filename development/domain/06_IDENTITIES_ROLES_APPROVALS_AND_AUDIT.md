# Identities, Roles, Approvals, and Audit

- Document level: **1 — Architecture**
- Lifecycle state: Canonical

## Purpose

TaskControl changes operational systems and runs arbitrary user-defined actions. Governance is therefore part of the core domain, not a later user-interface enhancement.

The first local version may use a simplified single-user model, but commands, records, and state transitions must preserve actor identity and authorisation boundaries.

## Principal

A Principal is any authenticated identity that can request an action.

Principal types:

- User.
- ServiceIdentity.
- AgentIdentity.
- SystemProcess.

### Common attributes

- `principal_id`.
- Principal type.
- Display name.
- Authentication subject or provider reference.
- Lifecycle state.
- Organisation or tenant scope.
- Created and last-seen metadata.

## User

A User represents a human operator, developer, reviewer, administrator, or auditor.

User records should not own authentication secrets. Authentication belongs to a configured identity provider or secure local authentication mechanism.

## ServiceIdentity

A ServiceIdentity represents automation that calls the API or performs non-interactive deployment and execution actions.

It must have:

- Explicit purpose.
- Narrow permissions.
- Credential reference.
- Owner.
- Rotation metadata.
- Optional expiry.

## AgentIdentity

A future remote agent must authenticate as a target-bound identity with capabilities limited to observation, deployment, execution, and reporting for authorised scopes.

## Role

A Role is a named collection of permissions.

Suggested initial roles:

- Viewer.
- Operator.
- Author.
- Deployer.
- Approver.
- Administrator.
- Auditor.

Roles are conveniences; permission checks must operate on explicit permissions and scopes.

## Permission

A Permission authorises an action against a resource scope.

Examples:

- `task.read`.
- `task.create`.
- `task.publish`.
- `task.activate`.
- `execution.request`.
- `execution.cancel`.
- `profile.manage`.
- `secret_reference.manage`.
- `deployment.plan`.
- `deployment.apply`.
- `deployment.rollback`.
- `approval.decide`.
- `audit.read`.
- `administration.manage`.

### Scope model

Permissions may be constrained by:

- Organisation or tenant.
- Environment.
- Collection.
- Task.
- Inventory group.
- Target.

The local-first product may initially treat the local user as administrator while still invoking an AuthorisationService interface.

## Ownership

Ownership identifies the person or team accountable for a resource. It is not identical to permission.

A task owner may receive notifications and be asked to approve changes, but ownership alone does not automatically grant every administrative permission.

## ApprovalPolicy

An ApprovalPolicy defines when an operation requires review before proceeding.

Potential triggers:

- Activating a revision in production.
- Applying a deployment to high-risk targets.
- Using raw shell mode.
- Changing secret references.
- Applying to many targets.
- Cancelling a critical execution.
- Enabling fail-open condition behaviour.

### Policy attributes

- `approval_policy_id`.
- Scope.
- Operation types.
- Required approver roles or principals.
- Minimum decisions.
- Separation-of-duties rule.
- Expiry.
- Required evidence or comment.

## ApprovalRequest

An ApprovalRequest is an immutable request to authorise a specific proposed operation.

### Attributes

- `approval_request_id`.
- Operation type.
- Resource identifiers and immutable digests.
- Requested by and requested time.
- Reason.
- Required approver constraints.
- Expiry.
- Current state.
- Decision history.

The approved object must be immutable. If a deployment plan changes, a new approval is required.

### States

- Pending.
- Approved.
- Rejected.
- Expired.
- Cancelled.
- Superseded.

## ApprovalDecision

A decision records:

- Approver.
- Decision.
- Time.
- Comment.
- Authentication strength metadata when applicable.
- Relevant conflict-of-interest checks.

A requester must not approve their own request when separation of duties applies.

## AuditEvent

An AuditEvent is an append-only record of a domain-significant fact or requested change.

### Required attributes

- `audit_event_id`.
- Occurred time.
- Actor principal.
- Action type.
- Resource type and identifier.
- Scope.
- Result: accepted, rejected, failed, or completed.
- Reason or justification.
- Correlation and causation identifiers.
- Before and after references or redacted snapshots.
- Client or source metadata.
- Integrity metadata when supported.

### Events that must be audited

- Authentication and material authorisation failures.
- Task lifecycle and revision changes.
- Profile and calendar publication.
- Runtime switch changes.
- Manual execution requests.
- Cancellation, retry, and replay.
- Deployment plan creation, approval, apply, rollback, and drift reconciliation.
- Target registration and retirement.
- Role and permission changes.
- Secret-reference metadata changes.
- Plugin installation, enablement, and configuration.
- Retention or deletion actions.

### Audit versus logs

Application logs explain software behaviour. Audit events explain who performed domain-significant actions.

Audit events must not be discarded simply because debug logging is disabled.

## Audit immutability

- Audit records are append-only.
- Corrections create new events referencing the incorrect event.
- Retention changes are themselves audited.
- Sensitive values are redacted.
- Future enterprise editions may use cryptographic chaining or external immutable storage.

## Reason requirements

High-risk operations should require a non-empty reason, including:

- Production deployment.
- Force cancellation.
- Manual override.
- Fail-open policy.
- Permission escalation.
- Drift acknowledgement without remediation.

## Session and request context

Every application-service command should receive a RequestContext containing:

- Principal.
- Correlation identifier.
- Request source.
- Client metadata.
- Optional reason.
- Optional impersonation metadata.

Do not access a global current user from domain logic.

## Impersonation

Administrative impersonation, if ever supported, must be explicit, visible, constrained, and audited with both acting and represented identities.

## Retention and privacy

Operational records may include usernames, paths, command arguments, and log output. Retention policy must distinguish:

- Audit events.
- Execution metadata.
- Logs.
- Evidence artefacts.
- Deployment artefacts.

Deletion or anonymisation must preserve integrity and regulatory obligations.

## API guidance

Recommended resources:

- `/users`.
- `/service-identities`.
- `/roles`.
- `/permissions`.
- `/approval-requests`.
- `/audit-events`.

Domain commands must perform authorisation in the application layer even when route-level checks also exist.

## CLI guidance

```text
taskctl approval list
taskctl approval show <id>
taskctl approval approve <id> --comment ...
taskctl audit list --resource task:<id>
taskctl role show operator
```

## UI guidance

- Show why an operation is unavailable.
- Display approval requirements before the user invests in a plan.
- Provide an audit timeline on significant resources.
- Distinguish ownership from access.
- Require reason fields for high-risk actions.
- Avoid exposing permissions as unexplained internal codes only.

## Validation rules

- Disabled principals cannot request new actions.
- Permissions must be evaluated for resource scope.
- Approval must reference an immutable operation digest.
- Expired or rejected approval cannot authorise action.
- Self-approval is blocked when separation of duties applies.
- Audit writes must be transactionally associated with domain changes where practical.
- Secret values never enter audit snapshots.

## Future extensions

- SSO and OIDC.
- SCIM provisioning.
- Enterprise directory groups.
- Policy engines.
- Time-bound privileged access.
- Break-glass procedures.
- Cryptographically chained audit logs.
- Compliance exports.
- Delegated tenant administration.
