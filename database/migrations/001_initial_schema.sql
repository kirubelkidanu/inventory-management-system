-- ==============================================================================
-- Migration: 001_initial_schema.sql
-- Description: Initial database foundation for the Inventory Management System.
-- Author: Implementation Agent
-- Date: 2026-08-15
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. EXTENSIONS
-- ------------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ------------------------------------------------------------------------------
-- 2. USERS & ACCESS CONTROL
-- ------------------------------------------------------------------------------
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id UUID UNIQUE NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('ADMIN', 'INVENTORY_MANAGER', 'STORE_KEEPER', 'VIEWER')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------------------------
-- 3. PROJECTS & LOCATIONS
-- ------------------------------------------------------------------------------
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    location VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------------------------
-- 4. WAREHOUSES / STORES
-- ------------------------------------------------------------------------------
CREATE TABLE warehouses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    location VARCHAR(255),
    default_project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------------------------
-- 5. ITEM CATEGORIES
-- ------------------------------------------------------------------------------
CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------------------------
-- 6. ITEM MASTER CATALOG
-- ------------------------------------------------------------------------------
CREATE TABLE items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_code VARCHAR(100) UNIQUE NOT NULL,
    description TEXT NOT NULL,
    category_id UUID NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    default_unit VARCHAR(50) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------------------------
-- 7. INVENTORY BALANCES (CURRENT-STATE PROJECTION)
-- ------------------------------------------------------------------------------
CREATE TABLE inventory_balances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    warehouse_id UUID NOT NULL REFERENCES warehouses(id) ON DELETE RESTRICT,
    item_id UUID NOT NULL REFERENCES items(id) ON DELETE RESTRICT,
    quantity_on_hand NUMERIC(15, 4) NOT NULL DEFAULT 0.0000 CHECK (quantity_on_hand >= 0),
    quantity_reserved NUMERIC(15, 4) NOT NULL DEFAULT 0.0000 CHECK (quantity_reserved >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_inventory_balances_wh_item UNIQUE (warehouse_id, item_id)
);

-- ------------------------------------------------------------------------------
-- 8. TRANSACTIONS (VOUCHER HEADERS)
-- ------------------------------------------------------------------------------
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_number VARCHAR(100) UNIQUE NOT NULL,
    transaction_type VARCHAR(20) NOT NULL CHECK (transaction_type IN ('GRV', 'SIV', 'ISTV', 'ISTRV', 'SRV', 'ADJUSTMENT')),
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'POSTED', 'CANCELLED', 'CORRECTED', 'PARTIALLY_RECEIVED', 'COMPLETED')),
    transaction_date DATE NOT NULL DEFAULT CURRENT_DATE,
    
    -- Warehouse & project associations
    warehouse_id UUID REFERENCES warehouses(id) ON DELETE RESTRICT,
    source_warehouse_id UUID REFERENCES warehouses(id) ON DELETE RESTRICT,
    destination_warehouse_id UUID REFERENCES warehouses(id) ON DELETE RESTRICT,
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    
    -- Transaction references
    reference_transaction_id UUID REFERENCES transactions(id) ON DELETE RESTRICT,
    external_reference VARCHAR(100),
    
    -- Physical GRV Voucher Fields
    supplier_name VARCHAR(255),
    invoice_no VARCHAR(100),
    received_grv_no VARCHAR(100),
    store_no VARCHAR(100),
    
    -- Physical SIV Voucher Fields
    requested_from VARCHAR(255),
    project_dept VARCHAR(255),
    requested_no VARCHAR(100),
    siv_no VARCHAR(100),
    issued_by_name VARCHAR(255),
    checked_by_name VARCHAR(255),
    received_by_name VARCHAR(255),
    approved_by_name VARCHAR(255),
    
    -- Physical ISTV Transfer Voucher Fields
    istv_no VARCHAR(100),
    plate_no VARCHAR(100),
    driver_name VARCHAR(255),
    material_summary VARCHAR(255),
    
    -- Adjustment reason & general remarks
    adjustment_reason TEXT,
    remarks TEXT,
    
    -- Audit & Lifecycle tracking
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    posted_by UUID REFERENCES users(id) ON DELETE RESTRICT,
    posted_at TIMESTAMPTZ,
    cancelled_by UUID REFERENCES users(id) ON DELETE RESTRICT,
    cancelled_at TIMESTAMPTZ,
    cancellation_reason TEXT,
    
    -- Structural Constraints
    CONSTRAINT chk_transaction_warehouse_requirement CHECK (
        (transaction_type IN ('GRV', 'SIV', 'SRV', 'ADJUSTMENT') AND warehouse_id IS NOT NULL)
        OR (transaction_type = 'ISTV' AND source_warehouse_id IS NOT NULL AND destination_warehouse_id IS NOT NULL AND source_warehouse_id != destination_warehouse_id)
        OR (transaction_type = 'ISTRV' AND destination_warehouse_id IS NOT NULL AND reference_transaction_id IS NOT NULL)
    ),
    CONSTRAINT chk_srv_reference CHECK (
        transaction_type != 'SRV' OR reference_transaction_id IS NOT NULL
    ),
    CONSTRAINT chk_adjustment_reason CHECK (
        transaction_type != 'ADJUSTMENT' OR adjustment_reason IS NOT NULL
    ),
    CONSTRAINT chk_cancellation_reason CHECK (
        status != 'CANCELLED' OR cancellation_reason IS NOT NULL
    )
);

-- ------------------------------------------------------------------------------
-- 9. TRANSACTION LINES (VOUCHER DETAILS)
-- ------------------------------------------------------------------------------
CREATE TABLE transaction_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    line_number INTEGER NOT NULL CHECK (line_number > 0),
    item_id UUID NOT NULL REFERENCES items(id) ON DELETE RESTRICT,
    quantity NUMERIC(15, 4) NOT NULL CHECK (quantity > 0),
    unit VARCHAR(50) NOT NULL,
    remarks TEXT,
    CONSTRAINT uq_transaction_line_index UNIQUE (transaction_id, line_number),
    CONSTRAINT uq_transaction_item UNIQUE (transaction_id, item_id)
);

-- ------------------------------------------------------------------------------
-- 10. STOCK MOVEMENTS (IMMUTABLE HISTORICAL EVENT LEDGER)
-- ------------------------------------------------------------------------------
CREATE TABLE stock_movements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL REFERENCES transactions(id) ON DELETE RESTRICT,
    transaction_line_id UUID NOT NULL REFERENCES transaction_lines(id) ON DELETE RESTRICT,
    item_id UUID NOT NULL REFERENCES items(id) ON DELETE RESTRICT,
    warehouse_id UUID NOT NULL REFERENCES warehouses(id) ON DELETE RESTRICT,
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    movement_type VARCHAR(20) NOT NULL CHECK (movement_type IN ('IN', 'OUT')),
    quantity NUMERIC(15, 4) NOT NULL CHECK (quantity > 0),
    signed_quantity NUMERIC(15, 4) NOT NULL,
    running_balance NUMERIC(15, 4),
    movement_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_movement_sign CHECK (
        (movement_type = 'IN' AND signed_quantity = quantity AND signed_quantity > 0)
        OR (movement_type = 'OUT' AND signed_quantity = -quantity AND signed_quantity < 0)
    )
);

-- ------------------------------------------------------------------------------
-- 11. STOCK MOVEMENTS IMMUTABILITY TRIGGER
-- ------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION prevent_movement_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'stock_movements is an immutable append-only ledger. Updates and deletions are prohibited.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_protect_stock_movements
BEFORE UPDATE OR DELETE ON stock_movements
FOR EACH ROW EXECUTE FUNCTION prevent_movement_mutation();

-- ------------------------------------------------------------------------------
-- 12. TRANSFER RECORDS (IN-TRANSIT TRACKING)
-- ------------------------------------------------------------------------------
CREATE TABLE transfer_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    istv_transaction_id UUID UNIQUE NOT NULL REFERENCES transactions(id) ON DELETE RESTRICT,
    source_warehouse_id UUID NOT NULL REFERENCES warehouses(id) ON DELETE RESTRICT,
    destination_warehouse_id UUID NOT NULL REFERENCES warehouses(id) ON DELETE RESTRICT,
    plate_no VARCHAR(100),
    driver_name VARCHAR(255),
    status VARCHAR(30) NOT NULL DEFAULT 'IN_TRANSIT' CHECK (status IN ('IN_TRANSIT', 'PARTIALLY_RECEIVED', 'COMPLETED', 'CANCELLED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- ------------------------------------------------------------------------------
-- 13. TRANSFER LINES (ITEM-LEVEL IN-TRANSIT & REMAINING RECONCILIATION)
-- ------------------------------------------------------------------------------
CREATE TABLE transfer_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transfer_record_id UUID NOT NULL REFERENCES transfer_records(id) ON DELETE RESTRICT,
    item_id UUID NOT NULL REFERENCES items(id) ON DELETE RESTRICT,
    sent_quantity NUMERIC(15, 4) NOT NULL CHECK (sent_quantity > 0),
    received_quantity NUMERIC(15, 4) NOT NULL DEFAULT 0.0000 CHECK (received_quantity >= 0),
    remaining_quantity NUMERIC(15, 4) GENERATED ALWAYS AS (sent_quantity - received_quantity) STORED CHECK (remaining_quantity >= 0),
    CONSTRAINT uq_transfer_lines_record_item UNIQUE (transfer_record_id, item_id)
);

-- ------------------------------------------------------------------------------
-- 14. AUDIT LOGS
-- ------------------------------------------------------------------------------
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL CHECK (action IN ('CREATE', 'UPDATE', 'POST', 'CANCEL', 'CORRECT', 'IMPORT', 'DELETE')),
    entity_type VARCHAR(100) NOT NULL,
    entity_id VARCHAR(100) NOT NULL,
    before_state JSONB,
    after_state JSONB,
    change_summary TEXT,
    reason TEXT,
    ip_address VARCHAR(45),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------------------------
-- 15. IMPORT BATCHES & IMPORT ERRORS (SPREADSHEET STAGING)
-- ------------------------------------------------------------------------------
CREATE TABLE import_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_number VARCHAR(100) UNIQUE NOT NULL,
    import_type VARCHAR(50) NOT NULL CHECK (import_type IN ('ITEM_MASTER', 'INITIAL_STOCK', 'WAREHOUSES', 'PROJECTS')),
    file_name VARCHAR(255) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    total_rows INTEGER NOT NULL DEFAULT 0,
    valid_rows INTEGER NOT NULL DEFAULT 0,
    error_rows INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(30) NOT NULL DEFAULT 'UPLOADED' CHECK (status IN ('UPLOADED', 'PARSED', 'VALIDATED', 'IMPORTING', 'COMPLETED', 'FAILED')),
    staged_data JSONB,
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE import_errors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE,
    row_number INTEGER NOT NULL,
    column_name VARCHAR(100),
    raw_value TEXT,
    error_code VARCHAR(100) NOT NULL,
    error_message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------------------------
-- 16. INDEXES
-- ------------------------------------------------------------------------------
-- Users
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_auth_id ON users(auth_user_id);

-- Projects & Warehouses
CREATE INDEX idx_projects_code ON projects(code);
CREATE INDEX idx_projects_is_active ON projects(is_active);
CREATE INDEX idx_warehouses_code ON warehouses(code);
CREATE INDEX idx_warehouses_default_project ON warehouses(default_project_id);

-- Categories & Items
CREATE INDEX idx_categories_code ON categories(code);
CREATE INDEX idx_items_item_code ON items(item_code);
CREATE INDEX idx_items_category_id ON items(category_id);
CREATE INDEX idx_items_description_trgm ON items USING gin (description gin_trgm_ops);

-- Inventory Balances
CREATE INDEX idx_inventory_balances_item ON inventory_balances(item_id);
CREATE INDEX idx_inventory_balances_qty ON inventory_balances(quantity_on_hand);

-- Transactions
CREATE INDEX idx_transactions_number ON transactions(transaction_number);
CREATE INDEX idx_transactions_type_status ON transactions(transaction_type, status);
CREATE INDEX idx_transactions_date ON transactions(transaction_date);
CREATE INDEX idx_transactions_wh ON transactions(warehouse_id);
CREATE INDEX idx_transactions_src_wh ON transactions(source_warehouse_id);
CREATE INDEX idx_transactions_dst_wh ON transactions(destination_warehouse_id);
CREATE INDEX idx_transactions_project ON transactions(project_id);
CREATE INDEX idx_transactions_reference ON transactions(reference_transaction_id);
CREATE INDEX idx_transactions_invoice_no ON transactions(invoice_no);
CREATE INDEX idx_transactions_plate_no ON transactions(plate_no);

-- Transaction Lines
CREATE INDEX idx_tx_lines_tx_id ON transaction_lines(transaction_id);
CREATE INDEX idx_tx_lines_item_id ON transaction_lines(item_id);

-- Stock Movements
CREATE INDEX idx_stock_movements_item_wh_date ON stock_movements(item_id, warehouse_id, movement_date);
CREATE INDEX idx_stock_movements_wh_date ON stock_movements(warehouse_id, movement_date);
CREATE INDEX idx_stock_movements_tx_id ON stock_movements(transaction_id);
CREATE INDEX idx_stock_movements_project ON stock_movements(project_id);

-- Transfer Records & Lines
CREATE INDEX idx_transfer_records_status ON transfer_records(status);
CREATE INDEX idx_transfer_records_src_dst ON transfer_records(source_warehouse_id, destination_warehouse_id);
CREATE INDEX idx_transfer_lines_record ON transfer_lines(transfer_record_id);
CREATE INDEX idx_transfer_lines_item ON transfer_lines(item_id);

-- Audit Logs & Import Staging
CREATE INDEX idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_logs_actor ON audit_logs(actor_user_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX idx_import_batches_status ON import_batches(status);
CREATE INDEX idx_import_errors_batch ON import_errors(batch_id, row_number);

-- ------------------------------------------------------------------------------
-- 17. RECONCILIATION VIEW (vw_reconciliation_discrepancies)
-- ------------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_reconciliation_discrepancies AS
WITH ledger_summary AS (
    SELECT 
        warehouse_id,
        item_id,
        COALESCE(SUM(signed_quantity), 0.0000) AS cumulative_ledger_quantity
    FROM stock_movements
    GROUP BY warehouse_id, item_id
)
SELECT 
    COALESCE(b.warehouse_id, l.warehouse_id) AS warehouse_id,
    w.code AS warehouse_code,
    w.name AS warehouse_name,
    COALESCE(b.item_id, l.item_id) AS item_id,
    i.item_code,
    i.description AS item_description,
    COALESCE(b.quantity_on_hand, 0.0000) AS projected_balance,
    COALESCE(l.cumulative_ledger_quantity, 0.0000) AS ledger_cumulative_balance,
    (COALESCE(b.quantity_on_hand, 0.0000) - COALESCE(l.cumulative_ledger_quantity, 0.0000)) AS discrepancy
FROM inventory_balances b
FULL OUTER JOIN ledger_summary l 
    ON b.warehouse_id = l.warehouse_id AND b.item_id = l.item_id
JOIN warehouses w ON w.id = COALESCE(b.warehouse_id, l.warehouse_id)
JOIN items i ON i.id = COALESCE(b.item_id, l.item_id)
WHERE (COALESCE(b.quantity_on_hand, 0.0000) - COALESCE(l.cumulative_ledger_quantity, 0.0000)) != 0.0000;
