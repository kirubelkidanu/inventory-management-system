-- Migration 004: Add unit_price support to transaction_lines
-- Supports valuation and unit price / unit cost tracking across transactions (including Opening Balances, GRV, etc.)

ALTER TABLE transaction_lines
ADD COLUMN IF NOT EXISTS unit_price NUMERIC(15, 4) NULL CHECK (unit_price >= 0);

COMMENT ON COLUMN transaction_lines.unit_price IS 'Unit purchase price or valuation cost per unit measurement. Must be >= 0 if provided.';
