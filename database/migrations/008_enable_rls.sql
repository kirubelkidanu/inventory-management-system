-- Migration 008: Enable Row Level Security (RLS) & PostgREST Lockdown
-- Implements ADR-008 (APPROVED) and docs/SECURITY.md production hardening.
--
-- Architecture notes:
-- - All application writes and RBAC checks flow through the FastAPI backend
--   using a privileged PostgreSQL connection (which bypasses RLS).
-- - Enabling RLS with no permissive policies for `anon` / `authenticated`
--   blocks direct PostgREST table access from browser clients while preserving
--   backend Service/TransactionService atomic operations.
-- - Direct `anon` privileges are revoked across all 14 tables and the
--   reconciliation view, `authenticated` write privileges are revoked on all
--   14 tables, and `vw_reconciliation_discrepancies` is set to
--   `security_invoker = true` so caller permissions apply on view access.

BEGIN;

-- 1. Enable Row Level Security on all 14 public tables
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.warehouses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inventory_balances ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transaction_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stock_movements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transfer_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transfer_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.import_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.import_errors ENABLE ROW LEVEL SECURITY;

-- 2. Revoke all privileges from `anon` on all 14 tables and reconciliation view
REVOKE ALL ON TABLE public.users FROM anon;
REVOKE ALL ON TABLE public.projects FROM anon;
REVOKE ALL ON TABLE public.warehouses FROM anon;
REVOKE ALL ON TABLE public.categories FROM anon;
REVOKE ALL ON TABLE public.items FROM anon;
REVOKE ALL ON TABLE public.inventory_balances FROM anon;
REVOKE ALL ON TABLE public.transactions FROM anon;
REVOKE ALL ON TABLE public.transaction_lines FROM anon;
REVOKE ALL ON TABLE public.stock_movements FROM anon;
REVOKE ALL ON TABLE public.transfer_records FROM anon;
REVOKE ALL ON TABLE public.transfer_lines FROM anon;
REVOKE ALL ON TABLE public.audit_logs FROM anon;
REVOKE ALL ON TABLE public.import_batches FROM anon;
REVOKE ALL ON TABLE public.import_errors FROM anon;
REVOKE ALL ON TABLE public.vw_reconciliation_discrepancies FROM anon;

-- 3. Revoke direct write privileges from `authenticated` on all 14 tables
REVOKE INSERT, UPDATE, DELETE ON TABLE public.users FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON TABLE public.projects FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON TABLE public.warehouses FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON TABLE public.categories FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON TABLE public.items FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON TABLE public.inventory_balances FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON TABLE public.transactions FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON TABLE public.transaction_lines FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON TABLE public.stock_movements FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON TABLE public.transfer_records FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON TABLE public.transfer_lines FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON TABLE public.audit_logs FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON TABLE public.import_batches FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON TABLE public.import_errors FROM authenticated;

-- 4. Enforce invoker security context on the reconciliation discrepancy view
ALTER VIEW public.vw_reconciliation_discrepancies SET (security_invoker = true);

COMMIT;
