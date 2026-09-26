# Security

## Principles

1. Never trust browser input.
2. Never expose secrets.
3. Never allow unauthorized stock changes.
4. Never silently destroy inventory history.
5. Make important actions auditable.
6. Use database constraints in addition to application validation.

## Authentication

Use Supabase Auth.

The frontend receives authenticated session information. Backend endpoints must verify the authenticated identity and authorization.

## Authorization

Roles:
- Admin
- Inventory Manager
- Store Keeper
- Viewer

Permissions must be enforced by backend policy.

Frontend button hiding is only a UX feature, not security.

## Secrets

Never commit:
- Supabase service-role key
- database password
- API keys
- JWT secrets
- deployment secrets

Use:
- `.env` locally
- deployment platform secret storage in production
- `.env.example` containing names only

## Supabase

Use the public/anon key only where appropriate on the client.

The service-role/secret key is server-side only.

RLS must be enabled/configured for tables exposed through client-accessible Supabase APIs.

## Database security

Use:
- foreign keys
- CHECK constraints
- unique constraints
- NOT NULL where appropriate
- least-privilege database access
- migrations

## Transaction security

Stock-changing operations must be atomic.

Never:
- fetch balance
- calculate in frontend
- send new balance
- overwrite database balance

Instead, execute the business operation server-side/database-side using a transaction/locking strategy appropriate for PostgreSQL.

## Concurrency

Two users issuing stock simultaneously must not both see the same old balance and overspend it.

Use appropriate database transactions and row-level locking/atomic update patterns.

This is a critical requirement.

## Audit

Log:
- transaction creation
- posting
- correction
- adjustment
- user/role changes
- important configuration changes

## Data deletion

Do not hard-delete posted transactions.

Use status/correction/reversal patterns where required.

## Validation

Validate:
- item exists
- warehouse exists
- project exists
- quantity is valid
- unit matches item
- source/destination are valid
- reference transaction is valid
- available quantity is sufficient
- user has permission

## Production

Before production:
- review RLS
- verify secrets
- enable HTTPS
- test backups/recovery process
- disable debug mode
- verify CORS
- verify error messages do not leak secrets or stack traces
- run security tests
