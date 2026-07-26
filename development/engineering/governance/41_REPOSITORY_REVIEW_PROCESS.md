# Repository Review Process

Every substantial development wave ends with a repository-level review, not only a review of changed lines.

## Review perspectives

### Architecture

- Are layer boundaries and dependency direction preserved?
- Did a new shortcut bypass a service, port, policy, or adapter?
- Are new dependencies and extension points justified?
- Has the change created circular or hidden coupling?

### Domain

- Does behaviour use the established ubiquitous language?
- Are aggregate ownership and invariants preserved?
- Are state and failure classifications still precise?
- Did transport or persistence representations become mistaken for domain truth?

### Data and compatibility

- Are migrations safe, ordered, and recoverable?
- Are API, CLI, configuration, and stored-data compatibility effects documented?
- Are immutable history and audit evidence preserved?

### Security

- Are authentication and authorisation enforced in application paths?
- Can secrets or sensitive data reach logs, errors, plans, or audits?
- Are new inputs, commands, callbacks, files, and plugins validated?

### Operations

- Can the feature be observed, diagnosed, reconciled, and recovered?
- Are correlation IDs and metrics sufficient?
- Are timeout, retry, cancellation, duplicate delivery, and partial failure handled?

### Quality and knowledge

- Do tests prove important success and failure behaviour?
- Is logic duplicated?
- Are names and contracts clear?
- Are documentation, examples, status, and decisions current?

## Review severity

- **Blocker:** correctness, data integrity, security, or architectural violation that must be fixed before merge.
- **Major:** maintainability, reliability, observability, compatibility, or test deficiency requiring resolution or explicit approval.
- **Minor:** local clarity or consistency issue that should normally be corrected.
- **Follow-up:** valid deferred improvement with recorded owner, rationale, and scope.

## Review output

A review should state:

1. reviewed scope;
2. findings by perspective and severity;
3. evidence or affected paths;
4. required corrections;
5. accepted follow-ups;
6. final merge recommendation.

Approval means the reviewer believes the change satisfies the engineering definition of done; it does not merely mean the code runs.
