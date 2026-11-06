# Architecture Decisions

This file records important decisions that must remain consistent throughout development.

---

## ADR-001 — Inventory Dual Write

Status: APPROVED

Inventory-changing transactions update both:

- inventory_balances
- stock_movements

Both writes occur inside the same PostgreSQL transaction.

The TransactionService controls this process.

---

## ADR-002 — Inventory Authority

Status: APPROVED

inventory_balances.quantity_on_hand is the authoritative current-state projection.

stock_movements provides the historical ledger.

The cumulative signed quantity of stock_movements is used for reconciliation.

---

## ADR-003 — Immutable Stock Ledger

Status: APPROVED

stock_movements is append-only.

UPDATE and DELETE operations are prohibited.

Corrections must be represented through new transactions/movements rather than modifying historical movements.

---

## ADR-004 — Physical Movement Types

Status: APPROVED

stock_movements supports only:

- IN
- OUT

Transfers and in-transit quantities are represented using transfer_records and transfer_lines.

---

## ADR-005 — Transfer Receiving

Status: APPROVED

Transfers support:

- full receiving
- partial receiving
- remaining quantity tracking

Over-receiving must never be allowed.

---

## ADR-006 — Transaction Lines

Status: APPROVED

An item may occur only once within a transaction voucher.

Database constraint:

UNIQUE(transaction_id, item_id)

---

## ADR-007 — Database Triggers

Status: APPROVED

Triggers must not automatically maintain inventory_balances from stock_movements.

Inventory changes are explicitly controlled by TransactionService.

---

## ADR-008 — RLS

Status: CURRENT DEVELOPMENT DECISION

Supabase Row Level Security is currently disabled.

RLS/security policy implementation will be addressed deliberately during the authentication and authorization phase.

Do not enable RLS automatically without reviewing the application authorization architecture first.


---

## ADR-009 — Opening Balance and Unit Price Valuation Support

Status: APPROVED

1. Transaction Lines Valuation:
   - `transaction_lines.unit_price` is tracked as `NUMERIC(15, 4) NULL CHECK (unit_price >= 0)`.
   - Line total price is computed as `quantity * unit_price`.

2. 4-Column Initial Stock Ingestion:
   - Initial stock staging supports 4-column sheets (`inventory id`, `quantity`, `unit measurment`, `unit price`).
   - Blank unit of measurement falls back to the item's configured `default_unit`.
   - Blank or omitted `unit_price` defaults to `0.0000`.
   - Staging surfaces explicit duplicates (`DUPLICATE_IN_FILE`) and existing warehouse stock (`ALREADY_EXISTS`) so clean items can be committed safely without duplicate stock creation.

3. Transaction Ledger Semantics:
   - Opening balances are posted through `TransactionService.create_and_post_opening_balance` under single atomic PostgreSQL transactions.
   - Headers use `transaction_type = 'ADJUSTMENT'`, `adjustment_reason = 'Opening Balance'`, and `external_reference = 'OPENING_BALANCE'`.
   - Inventory quantities update `inventory_balances` with row-level locks (`SELECT FOR UPDATE`) and append immutable `IN` records to `stock_movements`.

---

## ADR-010 — Ledger-Safe Item Deletion and Soft Archival (Option A)

Status: APPROVED

1. Referential Integrity & Invariant Protection:
   - Items in the master catalog (items) cannot be hard-deleted if they are referenced by historical ledger records (	ransaction_lines, stock_movements, 	ransfer_lines) or hold non-zero stock (inventory_balances.quantity_on_hand > 0 or quantity_reserved > 0).
   - If referenced or holding stock, attempting to delete the item safely transitions it to is_active = FALSE (soft-archived) and records an AuditLog entry (ction='UPDATE').
   - If completely unused (zero references and only zero-quantity balance records, if any), the zero-quantity balances are pruned first and the item is permanently deleted (ction='DELETE').

2. Role-Based Access Control:
   - Only users with the ADMIN role are permitted to delete or bulk-delete items (DELETE /api/v1/items/{item_id} and POST /api/v1/items/bulk-delete) or restore archived items (PATCH /api/v1/items/{item_id}/restore).
   - Non-admin roles (STORE_KEEPER, INVENTORY_MANAGER, VIEWER) receive 403 Forbidden.

3. Catalog Listing & Search:
   - GET /api/v1/items defaults to returning only active items (is_active = TRUE).
   - An explicit include_inactive=true query parameter exposes archived items for administrative audits and restoration.

---

## ADR-011 — Resilient 3-Tier JWT Authentication & User Provisioning

Status: APPROVED

1. Token Verification:
   - Supabase Bearer JWT tokens are validated via a 3-tier architecture:
     - Tier 1: Supabase Auth HTTP verification endpoint (`/auth/v1/user`) with environment-sanitized URL and publishable key.
     - Tier 2: Asymmetric ES256 (ECC P-256) public key signature verification via Supabase JWKS (`/.well-known/jwks.json`), backed by an in-memory cache and static production fallback JWK.
     - Tier 3: Local symmetric HS256 secret verification (test suite and local development).
   - If all tiers fail, HTTP 401 returns detailed multi-tier diagnostic failure descriptions.

2. User Profile Linking & Provisioning:
   - When a valid Supabase token is authenticated:
     1. Match `public.users.auth_user_id == UUID(sub)`.
     2. Fallback: match `public.users.email ILIKE token.email` -> link `auth_user_id` and activate user.
     3. Fallback: if the authenticated user is the project administrator (`sabelkidanu@gmail.com` or `d3a1107b-b5a6-45bc-bcb2-981feb537d06`), auto-provision an active `ADMIN` user record in `public.users`.

