# Dependency Rules

- Document level: **1 — Architecture**
- Lifecycle state: Canonical

## Core direction

```text
Transport/UI -> Application -> Domain
Infrastructure/Adapters -> Ports defined by inner layers
```

Dependencies point inward. Inner layers never import outer frameworks.

## Allowed relationships

- API and CLI may depend on application services and transport schemas.
- Application services may depend on domain objects and ports.
- Domain objects may depend on other domain objects within an approved bounded-context relationship.
- Adapters may depend on external libraries and implement ports.
- Infrastructure may compose all concrete implementations at process startup.
- UI may depend on generated or documented API contracts.

## Forbidden relationships

- Domain -> FastAPI, Typer, SQLAlchemy, Alembic, React, scheduler SDKs, cloud SDKs.
- Application -> concrete database sessions, HTTP request objects, CLI context objects, vendor SDK clients.
- API/CLI -> direct database access for product operations.
- Persistence model -> ownership of business invariants.
- UI -> database or server repository implementation.
- One adapter -> another adapter as an undeclared shortcut.
- Tests -> production-only backdoors that cannot exist in real composition.

## Cross-context access

A bounded context should access another through an explicit application contract, domain event, or port. Direct mutation of another context's aggregates is prohibited.

## Import rules

- Avoid wildcard imports.
- Avoid import-time side effects.
- Keep optional integrations behind adapter modules.
- Do not resolve settings or create clients at module import time.
- Circular imports indicate misplaced ownership and must not be hidden with arbitrary local imports.

## Dependency additions

A new production dependency requires:

1. problem and use case;
2. why standard-library or existing capabilities are insufficient;
3. maintenance and security posture;
4. licence compatibility;
5. runtime and packaging impact;
6. test strategy;
7. removal or migration considerations.

## Enforcement

Use static checks where practical. Architectural tests should verify forbidden imports and layer boundaries once source packages exist.
