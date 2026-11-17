-- Migration 006: Add transaction line void tracking columns
-- Supports Option A: Atomic Single-Line Reversal (Compensating Ledger Pattern) per ADR-009 / ADR-012

ALTER TABLE transaction_lines
ADD COLUMN IF NOT EXISTS is_voided BOOLEAN NOT NULL DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS voided_by UUID NULL REFERENCES users(id) ON DELETE RESTRICT,
ADD COLUMN IF NOT EXISTS voided_at TIMESTAMPTZ NULL,
ADD COLUMN IF NOT EXISTS void_reason TEXT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_tx_line_void_reason'
    ) THEN
        ALTER TABLE transaction_lines
        ADD CONSTRAINT chk_tx_line_void_reason CHECK (is_voided = FALSE OR void_reason IS NOT NULL);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_tx_lines_is_voided ON transaction_lines(is_voided);
CREATE INDEX IF NOT EXISTS idx_tx_lines_voided_by ON transaction_lines(voided_by);

COMMENT ON COLUMN transaction_lines.is_voided IS 'Indicates whether this individual transaction line has been voided/reversed.';
COMMENT ON COLUMN transaction_lines.voided_by IS 'The user who authorized and performed the line voiding.';
COMMENT ON COLUMN transaction_lines.voided_at IS 'Timestamp when the line was voided.';
COMMENT ON COLUMN transaction_lines.void_reason IS 'Mandatory business explanation for voiding the transaction line.';
