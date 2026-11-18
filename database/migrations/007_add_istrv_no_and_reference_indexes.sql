-- Migration 007: Add istrv_no column to transactions and create reference lookup indexes
-- Strictly adhering to ADR-001 through ADR-008 and AGENTS.md

-- 1. Add istrv_no column to transactions table if it does not already exist
ALTER TABLE transactions
ADD COLUMN IF NOT EXISTS istrv_no VARCHAR(100) NULL;

-- 2. Create performance lookup indexes for physical voucher and document references
CREATE INDEX IF NOT EXISTS idx_transactions_received_grv_no ON transactions(received_grv_no);
CREATE INDEX IF NOT EXISTS idx_transactions_istv_no ON transactions(istv_no);
CREATE INDEX IF NOT EXISTS idx_transactions_istrv_no ON transactions(istrv_no);
CREATE INDEX IF NOT EXISTS idx_transactions_siv_no ON transactions(siv_no);
CREATE INDEX IF NOT EXISTS idx_transactions_requested_no ON transactions(requested_no);
CREATE INDEX IF NOT EXISTS idx_transactions_external_ref ON transactions(external_reference);
