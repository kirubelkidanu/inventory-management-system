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