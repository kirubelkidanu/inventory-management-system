# PostgreSQL Database Specification (Implementation-Ready)

## 1. System Overview & Core Principles

This specification defines the complete, production-grade PostgreSQL schema for the Inventory Management System. It enforces data integrity at both the application and database constraint levels.

### Key Architectural Invariants
1. **Current-State Projection (`inventory_balances`)**: Fast balance lookups, stock availability checks, and deterministic row-level locking (`SELECT ... FOR UPDATE`).
2. **Immutable Event Ledger (`stock_movements`)**: Every stock change creates permanent movement rows. Movements are NEVER updated or deleted.
3. **Atomic Dual-Write**: Transaction posting atomically updates `inventory_balances` and inserts into `stock_movements` within a single database transaction.
4. **Independent Warehouses & Projects**: Warehouses and projects are distinct entities. A warehouse may have an optional default project association, but is not bound to one.
5. **No Direct In-Place Mutation of Posted Data**: Posted transactions cannot be edited in place or deleted. Cancellations and adjustments use compensating transactions and audit logging.
6. **In-Transit Transfer Lifecycle**: `ISTV` decrements source warehouse stock and creates an in-transit transfer record. Destination stock increases ONLY when `ISTRV` is posted.
7. **Numeric Precision**: All quantities use `NUMERIC(15, 4)` for exact decimal precision without floating-point inaccuracies.
8. **Primary Keys**: Standardized on PostgreSQL `UUID` (`gen_random_uuid()`).

---

## 2. Complete Schema Definitions

### 2.1 `users`
Application user profiles mapped to Supabase Auth (`auth.users`).

| Column | Data Type | Constraints / Modifiers | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Internal user ID |
| `auth_user_id` | `UUID` | `UNIQUE NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE` | Supabase Auth UUID link |
| `email` | `VARCHAR(255)` | `UNIQUE NOT NULL` | User email address |
| `full_name` | `VARCHAR(255)` | `NOT NULL` | Display/Full name |
| `role` | `VARCHAR(50)` | `NOT NULL CHECK (role IN ('ADMIN', 'INVENTORY_MANAGER', 'STORE_KEEPER', 'VIEWER'))` | Application role |
| `is_active` | `BOOLEAN` | `NOT NULL DEFAULT TRUE` | Active/Inactive flag |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | Record creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | Record last update timestamp |

**Indexes**:
- `CREATE INDEX idx_users_role ON users(role);`
- `CREATE INDEX idx_users_auth_id ON users(auth_user_id);`

---

### 2.2 `projects`
Construction sites, departments, or project entities.

| Column | Data Type | Constraints / Modifiers | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Primary Key |
| `code` | `VARCHAR(50)` | `UNIQUE NOT NULL` | Unique project code (e.g. `PRJ-KZ-01`) |
| `name` | `VARCHAR(255)` | `NOT NULL` | Project name (e.g. `Kazanchis Project`) |
| `location` | `VARCHAR(255)` | `NULL` | Physical site location |
| `is_active` | `BOOLEAN` | `NOT NULL DEFAULT TRUE` | Active status |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | Update timestamp |

**Indexes**:
- `CREATE INDEX idx_projects_code ON projects(code);`
- `CREATE INDEX idx_projects_is_active ON projects(is_active);`

---

### 2.3 `warehouses`
Physical storage locations / stores. Independent from projects, with optional default association.

| Column | Data Type | Constraints / Modifiers | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Primary Key |
| `code` | `VARCHAR(50)` | `UNIQUE NOT NULL` | Unique warehouse code (e.g. `WH001`) |
| `name` | `VARCHAR(255)` | `NOT NULL` | Warehouse name |
| `location` | `VARCHAR(255)` | `NULL` | Physical location details |
| `default_project_id` | `UUID` | `NULL REFERENCES projects(id) ON DELETE SET NULL` | Optional associated project |
| `is_active` | `BOOLEAN` | `NOT NULL DEFAULT TRUE` | Active status |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | Update timestamp |

**Indexes**:
- `CREATE INDEX idx_warehouses_code ON warehouses(code);`
- `CREATE INDEX idx_warehouses_default_project ON warehouses(default_project_id);`

---

### 2.4 `categories`
Major classification categories for materials and spare parts.

| Column | Data Type | Constraints / Modifiers | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Primary Key |
| `code` | `VARCHAR(50)` | `UNIQUE NOT NULL` | Category code (e.g. `01`, `02`, `14`) |
| `name` | `VARCHAR(255)` | `NOT NULL` | Category name (e.g. `CEMENT`, `STEEL`) |
| `description` | `TEXT` | `NULL` | Optional description |
| `is_active` | `BOOLEAN` | `NOT NULL DEFAULT TRUE` | Active status |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | Update timestamp |

**Indexes**:
- `CREATE INDEX idx_categories_code ON categories(code);`

---

### 2.5 `items`
Inventory master catalog.

| Column | Data Type | Constraints / Modifiers | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Primary Key |
| `item_code` | `VARCHAR(100)` | `UNIQUE NOT NULL` | Unique inventory item code (e.g. `01-CM-00001`) |
| `description` | `TEXT` | `NOT NULL` | Full material/item description |
| `category_id` | `UUID` | `NOT NULL REFERENCES categories(id) ON DELETE RESTRICT` | Foreign key to category |
| `default_unit` | `VARCHAR(50)` | `NOT NULL` | Default unit of measure (e.g. `Pcs`, `Kg`, `M2`) |
| `is_active` | `BOOLEAN` | `NOT NULL DEFAULT TRUE` | Active status |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | Update timestamp |

**Indexes**:
- `CREATE INDEX idx_items_item_code ON items(item_code);`
- `CREATE INDEX idx_items_category_id ON items(category_id);`
- `CREATE INDEX idx_items_description_trgm ON items USING gin (description gin_trgm_ops);`

---

### 2.6 `inventory_balances`
Current-state projection table for real-time quantity lookups and concurrency control.

| Column | Data Type | Constraints / Modifiers | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Primary Key |
| `warehouse_id` | `UUID` | `NOT NULL REFERENCES warehouses(id) ON DELETE RESTRICT` | Warehouse location |
| `item_id` | `UUID` | `NOT NULL REFERENCES items(id) ON DELETE RESTRICT` | Inventory item |
| `quantity_on_hand` | `NUMERIC(15, 4)` | `NOT NULL DEFAULT 0.0000 CHECK (quantity_on_hand >= 0)` | Available physical stock (non-negative) |
| `quantity_reserved` | `NUMERIC(15, 4)` | `NOT NULL DEFAULT 0.0000 CHECK (quantity_reserved >= 0)` | Reserved stock (e.g. staged transfers/drafts) |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | Timestamp of last balance modification |

**Constraints**:
- `UNIQUE (warehouse_id, item_id)` (Strictly 1 balance row per warehouse/item pair)

**Indexes**:
- `CREATE UNIQUE INDEX uq_inventory_balances_wh_item ON inventory_balances(warehouse_id, item_id);`
- `CREATE INDEX idx_inventory_balances_item ON inventory_balances(item_id);`
- `CREATE INDEX idx_inventory_balances_qty ON inventory_balances(quantity_on_hand);`

---

### 2.7 `transactions`
Header table for all inventory transactions (GRV, SIV, ISTV, ISTRV, SRV, ADJUSTMENT).

| Column | Data Type | Constraints / Modifiers | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Primary Key |
| `transaction_number` | `VARCHAR(100)` | `UNIQUE NOT NULL` | Unique system transaction identifier |
| `transaction_type` | `VARCHAR(20)` | `NOT NULL CHECK (transaction_type IN ('GRV', 'SIV', 'ISTV', 'ISTRV', 'SRV', 'ADJUSTMENT'))` | Transaction type enum |
| `status` | `VARCHAR(30)` | `NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'POSTED', 'CANCELLED', 'CORRECTED', 'PARTIALLY_RECEIVED', 'COMPLETED'))` | Lifecycle status |
| `transaction_date` | `DATE` | `NOT NULL DEFAULT CURRENT_DATE` | Effective operational date |
| `warehouse_id` | `UUID` | `NULL REFERENCES warehouses(id) ON DELETE RESTRICT` | Primary warehouse / store location |
| `source_warehouse_id` | `UUID` | `NULL REFERENCES warehouses(id) ON DELETE RESTRICT` | Source warehouse (Required for ISTV) |
| `destination_warehouse_id`| `UUID` | `NULL REFERENCES warehouses(id) ON DELETE RESTRICT` | Destination warehouse (Required for ISTV/ISTRV) |
| `project_id` | `UUID` | `NULL REFERENCES projects(id) ON DELETE SET NULL` | Operational project association |
| `reference_transaction_id`| `UUID` | `NULL REFERENCES transactions(id) ON DELETE RESTRICT` | FK for ISTRV $\rightarrow$ ISTV, SRV $\rightarrow$ SIV, or reversals |
| `external_reference` | `VARCHAR(100)` | `NULL` | Generic external document reference |
| `supplier_name` | `VARCHAR(255)` | `NULL` | Supplier name (GRV) |
| `invoice_no` | `VARCHAR(100)` | `NULL` | Supplier invoice reference (GRV) |
| `received_grv_no` | `VARCHAR(100)` | `NULL` | Physical voucher number (GRV) |
| `store_no` | `VARCHAR(100)` | `NULL` | Physical store number (GRV) |
| `requested_from` | `VARCHAR(255)` | `NULL` | Requisitioning entity / unit (SIV) |
| `project_dept` | `VARCHAR(255)` | `NULL` | Requesting project / department (SIV) |
| `requested_no` | `VARCHAR(100)` | `NULL` | Requisition document reference number (SIV) |
| `siv_no` | `VARCHAR(100)` | `NULL` | Physical voucher number (SIV) |
| `issued_by_name` | `VARCHAR(255)` | `NULL` | Physical voucher issuer (SIV) |
| `checked_by_name` | `VARCHAR(255)` | `NULL` | Physical voucher verifier (SIV) |
| `received_by_name` | `VARCHAR(255)` | `NULL` | Physical voucher receiver (SIV) |
| `approved_by_name` | `VARCHAR(255)` | `NULL` | Physical voucher approver (SIV) |
| `istv_no` | `VARCHAR(100)` | `NULL` | Physical voucher number (ISTV) |
| `plate_no` | `VARCHAR(100)` | `NULL` | Transport vehicle plate number (ISTV) |
| `driver_name` | `VARCHAR(255)` | `NULL` | Transport driver name (ISTV) |
| `material_summary` | `VARCHAR(255)` | `NULL` | Header-level description / summary |
| `adjustment_reason` | `TEXT` | `NULL` | Mandatory reason for stock adjustments |
| `remarks` | `TEXT` | `NULL` | General notes / comments |
| `created_by` | `UUID` | `NOT NULL REFERENCES users(id) ON DELETE RESTRICT` | User who created the transaction |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | Creation timestamp |
| `posted_by` | `UUID` | `NULL REFERENCES users(id) ON DELETE RESTRICT` | User who posted the transaction |
| `posted_at` | `TIMESTAMPTZ` | `NULL` | Timestamp of posting |
| `cancelled_by` | `UUID` | `NULL REFERENCES users(id) ON DELETE RESTRICT` | User who cancelled the transaction |
| `cancelled_at` | `TIMESTAMPTZ` | `NULL` | Timestamp of cancellation |
| `cancellation_reason` | `TEXT` | `NULL` | Mandatory reason if cancelled |

**Table-Level CHECK Constraints**:
```sql
CONSTRAINT chk_istv_warehouses CHECK (
    transaction_type != 'ISTV' OR (
        source_warehouse_id IS NOT NULL 
        AND destination_warehouse_id IS NOT NULL 
        AND source_warehouse_id != destination_warehouse_id
    )
),
CONSTRAINT chk_istrv_reference CHECK (
    transaction_type != 'ISTRV' OR (
        reference_transaction_id IS NOT NULL 
        AND destination_warehouse_id IS NOT NULL
    )
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
```

**Indexes**:
- `CREATE INDEX idx_transactions_number ON transactions(transaction_number);`
- `CREATE INDEX idx_transactions_type_status ON transactions(transaction_type, status);`
- `CREATE INDEX idx_transactions_date ON transactions(transaction_date);`
- `CREATE INDEX idx_transactions_wh ON transactions(warehouse_id);`
- `CREATE INDEX idx_transactions_src_wh ON transactions(source_warehouse_id);`
- `CREATE INDEX idx_transactions_dst_wh ON transactions(destination_warehouse_id);`
- `CREATE INDEX idx_transactions_project ON transactions(project_id);`
- `CREATE INDEX idx_transactions_reference ON transactions(reference_transaction_id);`
- `CREATE INDEX idx_transactions_invoice_no ON transactions(invoice_no);`
- `CREATE INDEX idx_transactions_plate_no ON transactions(plate_no);`

---

### 2.8 `transaction_lines`
Item line details for each transaction voucher.

| Column | Data Type | Constraints / Modifiers | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Primary Key |
| `transaction_id` | `UUID` | `NOT NULL REFERENCES transactions(id) ON DELETE RESTRICT` | Parent transaction |
| `line_number` | `INTEGER` | `NOT NULL CHECK (line_number > 0)` | Sequential line index within voucher |
| `item_id` | `UUID` | `NOT NULL REFERENCES items(id) ON DELETE RESTRICT` | Item being transacted |
| `quantity` | `NUMERIC(15, 4)` | `NOT NULL CHECK (quantity > 0)` | Transacted quantity (always positive) |
| `unit` | `VARCHAR(50)` | `NOT NULL` | Unit of measure at time of transaction |
| `remarks` | `TEXT` | `NULL` | Line-level remarks / notes |

**Constraints**:
- `UNIQUE (transaction_id, line_number)`
- `UNIQUE (transaction_id, item_id)` (Prevents duplicate item rows on the same voucher)

**Indexes**:
- `CREATE INDEX idx_tx_lines_tx_id ON transaction_lines(transaction_id);`
- `CREATE INDEX idx_tx_lines_item_id ON transaction_lines(item_id);`

---

### 2.9 `stock_movements`
The immutable historical inventory event ledger. Every row is an append-only stock movement.

| Column | Data Type | Constraints / Modifiers | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Primary Key |
| `transaction_id` | `UUID` | `NOT NULL REFERENCES transactions(id) ON DELETE RESTRICT` | Originating transaction |
| `transaction_line_id` | `UUID` | `NOT NULL REFERENCES transaction_lines(id) ON DELETE RESTRICT` | Originating transaction line |
| `item_id` | `UUID` | `NOT NULL REFERENCES items(id) ON DELETE RESTRICT` | Item affected |
| `warehouse_id` | `UUID` | `NOT NULL REFERENCES warehouses(id) ON DELETE RESTRICT` | Warehouse affected |
| `project_id` | `UUID` | `NULL REFERENCES projects(id) ON DELETE SET NULL` | Project association at time of movement |
| `movement_type` | `VARCHAR(20)` | `NOT NULL CHECK (movement_type IN ('IN', 'OUT', 'IN_TRANSIT', 'OUT_TRANSIT'))` | Movement direction |
| `quantity` | `NUMERIC(15, 4)` | `NOT NULL CHECK (quantity > 0)` | Unsigned movement quantity |
| `signed_quantity` | `NUMERIC(15, 4)` | `NOT NULL` | Signed quantity (+quantity for IN, -quantity for OUT) |
| `running_balance` | `NUMERIC(15, 4)` | `NULL` | Running balance snapshot |
| `movement_date` | `DATE` | `NOT NULL` | Date of the movement |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | Immutable timestamp of ledger creation |

**Immutability Protection Trigger**:
```sql
CREATE OR REPLACE FUNCTION prevent_movement_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'stock_movements is an append-only ledger. Mutation or deletion is prohibited.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_protect_stock_movements
BEFORE UPDATE OR DELETE ON stock_movements
FOR EACH ROW EXECUTE FUNCTION prevent_movement_mutation();
```

**Indexes**:
- `CREATE INDEX idx_stock_movements_item_wh_date ON stock_movements(item_id, warehouse_id, movement_date);`
- `CREATE INDEX idx_stock_movements_wh_date ON stock_movements(warehouse_id, movement_date);`
- `CREATE INDEX idx_stock_movements_tx_id ON stock_movements(transaction_id);`
- `CREATE INDEX idx_stock_movements_project ON stock_movements(project_id);`

---

### 2.10 `transfer_records`
Lifecycle tracking for inter-store transfers (`ISTV` $\rightarrow$ `ISTRV`).

| Column | Data Type | Constraints / Modifiers | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Primary Key |
| `istv_transaction_id` | `UUID` | `UNIQUE NOT NULL REFERENCES transactions(id) ON DELETE RESTRICT` | Originating ISTV transaction |
| `source_warehouse_id` | `UUID` | `NOT NULL REFERENCES warehouses(id) ON DELETE RESTRICT` | Originating warehouse |
| `destination_warehouse_id`| `UUID` | `NOT NULL REFERENCES warehouses(id) ON DELETE RESTRICT` | Target destination warehouse |
| `plate_no` | `VARCHAR(100)` | `NULL` | Transport vehicle plate |
| `driver_name` | `VARCHAR(255)` | `NULL` | Transport driver name |
| `status` | `VARCHAR(30)` | `NOT NULL DEFAULT 'IN_TRANSIT' CHECK (status IN ('IN_TRANSIT', 'PARTIALLY_RECEIVED', 'COMPLETED', 'CANCELLED'))` | Transfer lifecycle state |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | Dispatch creation timestamp |
| `completed_at` | `TIMESTAMPTZ` | `NULL` | Final completion timestamp |

**Indexes**:
- `CREATE INDEX idx_transfer_records_status ON transfer_records(status);`
- `CREATE INDEX idx_transfer_records_src_dst ON transfer_records(source_warehouse_id, destination_warehouse_id);`

---

### 2.11 `transfer_lines`
Item-level in-transit tracking and remaining balance reconciliation.

| Column | Data Type | Constraints / Modifiers | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Primary Key |
| `transfer_record_id` | `UUID` | `NOT NULL REFERENCES transfer_records(id) ON DELETE RESTRICT` | Parent transfer record |
| `item_id` | `UUID` | `NOT NULL REFERENCES items(id) ON DELETE RESTRICT` | Item transferred |
| `sent_quantity` | `NUMERIC(15, 4)` | `NOT NULL CHECK (sent_quantity > 0)` | Dispatched quantity from source |
| `received_quantity` | `NUMERIC(15, 4)` | `NOT NULL DEFAULT 0.0000 CHECK (received_quantity >= 0)` | Cumulative quantity received at dest |
| `remaining_quantity` | `NUMERIC(15, 4)` | `GENERATED ALWAYS AS (sent_quantity - received_quantity) STORED CHECK (remaining_quantity >= 0)` | Remaining in-transit quantity |

**Constraints**:
- `UNIQUE (transfer_record_id, item_id)`
- `CHECK (received_quantity <= sent_quantity)` (Enforced by generated check)

**Indexes**:
- `CREATE INDEX idx_transfer_lines_record ON transfer_lines(transfer_record_id);`
- `CREATE INDEX idx_transfer_lines_item ON transfer_lines(item_id);`

---

### 2.12 `audit_logs`
Comprehensive audit trail for compliance, data modifications, and administrative events.

| Column | Data Type | Constraints / Modifiers | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Primary Key |
| `actor_user_id` | `UUID` | `NULL REFERENCES users(id) ON DELETE SET NULL` | Performing user |
| `action` | `VARCHAR(50)` | `NOT NULL CHECK (action IN ('CREATE', 'UPDATE', 'POST', 'CANCEL', 'CORRECT', 'IMPORT', 'DELETE'))` | Action type |
| `entity_type` | `VARCHAR(100)` | `NOT NULL` | Entity name (e.g. `transaction`, `item`) |
| `entity_id` | `VARCHAR(100)` | `NOT NULL` | Target entity identifier |
| `before_state` | `JSONB` | `NULL` | Snapshot prior to mutation |
| `after_state` | `JSONB` | `NULL` | Snapshot after mutation |
| `change_summary` | `TEXT` | `NULL` | Human-readable summary of changes |
| `reason` | `TEXT` | `NULL` | Mandatory reason for adjustments/corrections |
| `ip_address` | `VARCHAR(45)` | `NULL` | Client IP address |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | Audit entry timestamp |

**Indexes**:
- `CREATE INDEX idx_audit_logs_entity ON audit_logs(entity_type, entity_id);`
- `CREATE INDEX idx_audit_logs_actor ON audit_logs(actor_user_id);`
- `CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);`

---

### 2.13 `import_batches`
Staging header for bulk imports (Excel/CSV).

| Column | Data Type | Constraints / Modifiers | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Primary Key |
| `batch_number` | `VARCHAR(100)` | `UNIQUE NOT NULL` | Unique batch tracking number |
| `import_type` | `VARCHAR(50)` | `NOT NULL CHECK (import_type IN ('ITEM_MASTER', 'INITIAL_STOCK', 'WAREHOUSES', 'PROJECTS'))` | Import type |
| `file_name` | `VARCHAR(255)` | `NOT NULL` | Uploaded file name |
| `file_size_bytes` | `BIGINT` | `NOT NULL` | Upload file size in bytes |
| `total_rows` | `INTEGER` | `NOT NULL DEFAULT 0` | Total parsed rows in file |
| `valid_rows` | `INTEGER` | `NOT NULL DEFAULT 0` | Validated row count |
| `error_rows` | `INTEGER` | `NOT NULL DEFAULT 0` | Row count with validation errors |
| `status` | `VARCHAR(30)` | `NOT NULL DEFAULT 'UPLOADED' CHECK (status IN ('UPLOADED', 'PARSED', 'VALIDATED', 'IMPORTING', 'COMPLETED', 'FAILED'))` | Staging status |
| `staged_data` | `JSONB` | `NULL` | Staged parsed rows for preview before commit |
| `created_by` | `UUID` | `NOT NULL REFERENCES users(id) ON DELETE RESTRICT` | Uploading user |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | Upload timestamp |
| `completed_at` | `TIMESTAMPTZ` | `NULL` | Import execution timestamp |

**Indexes**:
- `CREATE INDEX idx_import_batches_status ON import_batches(status);`

---

### 2.14 `import_errors`
Row-level validation errors captured during Excel/CSV staging.

| Column | Data Type | Constraints / Modifiers | Description |
|---|---|---|---|
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Primary Key |
| `batch_id` | `UUID` | `NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE` | Parent import batch |
| `row_number` | `INTEGER` | `NOT NULL` | 1-indexed spreadsheet row number |
| `column_name` | `VARCHAR(100)` | `NULL` | Column identifier triggering error |
| `raw_value` | `TEXT` | `NULL` | Offending raw cell content |
| `error_code` | `VARCHAR(100)` | `NOT NULL` | Programmatic error code (e.g. `INVALID_UOM`) |
| `error_message` | `TEXT` | `NOT NULL` | Clear description of validation failure |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL DEFAULT NOW()` | Log timestamp |

**Indexes**:
- `CREATE INDEX idx_import_errors_batch ON import_errors(batch_id, row_number);`

---

## 3. Concurrency & Row-Locking Architecture

To guarantee zero race conditions and prevent negative stock:

### Deterministic Lock Acquisition Protocol
When posting any stock-changing transaction:
1. Identify all affected `(warehouse_id, item_id)` pairs.
2. Sort the pairs deterministically in ascending order by `(warehouse_id, item_id)`.
3. Execute `SELECT ... FOR UPDATE` on `inventory_balances` for those specific rows in that exact order.
4. Verify available quantity:
   $$\text{Available Stock} = \text{quantity\_on\_hand} - \text{quantity\_reserved}$$
5. If available stock is insufficient for an OUT movement (e.g. `SIV`, `ISTV`), rollback transaction immediately and raise an `INSUFFICIENT_STOCK` error.
6. Execute balance update and insert corresponding `stock_movements` atomically.
7. Commit database transaction.

```sql
-- Example Concurrency Safe Posting Query
SELECT warehouse_id, item_id, quantity_on_hand, quantity_reserved
FROM inventory_balances
WHERE (warehouse_id = $1 AND item_id = $2)
FOR UPDATE;
```

---

## 4. Reconciliation Engine Architecture

The system provides dual-layer reconciliation comparing the **current-state projection** against the **immutable movement ledger**.

### Reconciliation SQL View (`vw_reconciliation_discrepancies`)
```sql
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
```

---

## 5. Excel Import Staging Design

To ensure that spreadsheet imports never corrupt the database:

```text
Upload (XLSX/CSV) 
  → Parse (openpyxl) 
  → Staging (import_batches) 
  → Row-level Validation 
  → If errors: Log to import_errors & display error preview
  → If valid: Display Preview & Enable "Confirm Import" button
  → On Confirm: Execute atomic multi-row INSERT within a single DB transaction
```

---

## 6. Review Against System Requirements

| Requirement | How the Schema Enforces It |
|---|---|
| **Referential Integrity** | All foreign keys strictly defined with `ON DELETE RESTRICT` for financial and inventory links, and `ON DELETE SET NULL` only for optional project associations. |
| **Concurrency & Race Conditions** | Row-level locking on `inventory_balances` via `SELECT ... FOR UPDATE` in deterministic sorted key order. Check constraint `CHECK (quantity_on_hand >= 0)` guarantees database-level impossibility of negative stock. |
| **Duplicate Inventory** | Unique constraints on `items.item_code`, `warehouses.code`, `projects.code`, `categories.code`, `transactions.transaction_number`, `inventory_balances(warehouse_id, item_id)`, `transaction_lines(transaction_id, item_id)`. |
| **Transfer Consistency** | `transfer_records` linked 1-to-1 with `ISTV`, storing vehicle plate and driver name. `transfer_lines` tracks `sent_quantity`, `received_quantity`, and generated `remaining_quantity >= 0`. `ISTRV` receives against valid transfer records. |
| **Correction / Reversal Consistency** | Posted transactions cannot be deleted. Corrections link to original transaction via `reference_transaction_id`, generating balancing compensating movements in `stock_movements` with full audit logs. |
| **Auditability** | Complete `audit_logs` tracking every action, entity, actor, before/after JSONB state, and timestamps. Immutability trigger protects `stock_movements`. |
| **Reconciliation** | Built-in `vw_reconciliation_discrepancies` compares `inventory_balances.quantity_on_hand` against `SUM(signed_quantity)` in `stock_movements`. |

