# Architecture

## Goal

Use a modular monolith for the 15-day MVP. Keep the architecture simple, testable and easy for one developer plus a coding agent to maintain.

## High-level

```text
React + TypeScript
        |
        | HTTPS / JSON
        v
FastAPI Backend
        |
        +---- Authentication / Authorization
        |
        +---- Inventory Services
        |
        +---- Transaction Services
        |
        +---- Reporting Services
        |
        +---- Audit Services
        |
        v
PostgreSQL / Supabase
```

## Frontend

Recommended structure:

```text
frontend/
  src/
    components/
    pages/
    layouts/
    features/
      auth/
      inventory/
      warehouses/
      projects/
      transactions/
      reports/
      lookup/
    lib/
    hooks/
    types/
```

Use feature-oriented organization rather than one huge component.

## Backend

```text
backend/
  app/
    main.py
    api/
      routes/
    core/
    models/
    schemas/
    services/
    repositories/
    security/
    reports/
    audit/
  tests/
```

Keep business logic out of route handlers.

Example:
- Route validates request/authentication.
- Service applies business rules.
- Repository/data layer persists data.
- Database constraints provide final protection.

## Transaction service

All stock-changing operations should pass through a transaction service.

Examples:
- `create_grv()`
- `create_siv()`
- `create_istv()`
- `receive_istrv()`
- `create_srv()`
- `create_adjustment()`

The service must perform all related stock updates atomically.

## Database transaction

A stock operation must not partially succeed.

For example, ISTV must not:
1. reduce source stock,
2. then fail before creating in-transit data.

Use a database transaction so either the complete operation commits or everything rolls back.

## Reporting

Reports should read from transaction/movement data, not duplicated manually maintained report tables.

A balance view/query can be created for performance later.

## Deployment

MVP:
- Frontend: Vercel or equivalent.
- Backend: Render/Railway or equivalent.
- Database/Auth: Supabase.

Keep frontend and backend secrets separate.

## Agent development rule

Antigravity must not rewrite architecture merely because it prefers another framework or pattern. Changes to architecture require explicit approval.
