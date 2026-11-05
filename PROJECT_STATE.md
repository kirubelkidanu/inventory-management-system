## Current Phase

Official Project Sites & Warehouse Bin Locations Management Configured

## Project Status

The official 13 client project sites and corresponding warehouse bin locations have been fully seeded and integrated. Placeholder records (`WH001`, `WH002`, `PRJ-KZ-01`) have been safely archived without violating ledger immutability (`is_active = FALSE`, marked `[Archived]`). Full dynamic site and warehouse bin management has been implemented across the backend API, repositories, services, and frontend administration screens (`/warehouses` and `/projects`).
The entire backend and frontend enterprise inventory management platform is fully configured, secured, verified, seeded with live production master data and opening stock balances in Supabase PostgreSQL, and passes **220 tests** across 15 test modules with clean client production packaging.
Environment variable templates (`backend/.env.example`, `frontend/.env.example`, and root `.env.example`) strictly segregate server-side secrets from client-safe variables with zero committed credentials. Security middleware (`CORSMiddleware`), JWT authentication routes (`/api/v1/auth/token`, `/api/v1/auth/demo-login`, `/api/v1/auth/me`), and database stack trace sanitization are active in `backend/app/main.py`. The live PostgreSQL database is verified end-to-end with zero reconciliation discrepancies (`vw_reconciliation_discrepancies` == 0), dual-write balance/ledger immutability, in-transit transfer tracking, and authoritative Trial Balance reporting.

## Database Status

Migrations:
- database/migrations/001_initial_schema.sql (EXECUTED SUCCESSFULLY)
- database/migrations/002_expand_audit_log_actions.sql (EXECUTED SUCCESSFULLY)
- database/migrations/003_seed_official_sites_and_warehouses.sql (EXECUTED SUCCESSFULLY)
- database/migrations/004_add_unit_price_support.sql (EXECUTED SUCCESSFULLY)

Database foundation & Seeded Data:
- 14 tables created & 1 view active
- pg_trgm extension enabled
- Demo Users: 4 accounts seeded with foreign key links to `auth.users` (`admin@ims.local`, `manager@ims.local`, `storekeeper@ims.local`, `viewer@ims.local`)
- Official Sites: 13 active projects (`PRJ-KZ`, `PRJ-KL`, `PRJ-KL-GAR`, `PRJ-GR`, `PRJ-LM`, `PRJ-ET`, `PRJ-JM`, `PRJ-BS`, `PRJ-NK`, `PRJ-CK`, `PRJ-JM3`, `PRJ-HO`, `PRJ-AB`) + 1 archived (`PRJ-KZ-01`)
- Official Warehouse Bins: 13 active warehouses (`KZ-WH-001`, `KL-WH-001`, `KL-WH-002`, `GR-WH-001`, `LM-WH-001`, `ET-WH-001`, `JM-WH-001`, `BS-WH-001`, `NK-WH-001`, `CK-WH-001`, `JM3-WH-001`, `HO-WH-001`, `AB-WH-0001`) + 2 archived (`WH001`, `WH002`)
- Categories: 14 official categories (`01` through `14`) active
- Master Items: `01-CM-00001` (Cement), `02-ST-00001` (Rebar 12mm), `02-ST-00002` (Rebar 16mm), `07-PC-00001` (Anti-Rust Primer)
- Opening Balances (Strict ADR-001 Dual-Write): Opening GRV `GRV-20260919-CED420F0` posted via `TransactionService`:
  * Cement Grade 42.5N: 1,200 BAG
  * Rebar 12mm: 500 PCS
  * Rebar 16mm: 350 PCS
- Reconciliation view: 0 discrepancies (100% IN BALANCE)

RLS:
- Currently disabled.
- This is intentional for the current development stage.

## Database Architecture

### Inventory Dual-Write

Inventory changes must update:

1. inventory_balances
2. stock_movements

These writes must happen inside ONE atomic PostgreSQL transaction.

The backend TransactionService, ImportService, and ReconciliationService are responsible for coordinating these writes.

Database triggers must NOT automatically update inventory_balances from stock_movements.

### Inventory Balance

inventory_balances.quantity_on_hand is the authoritative current-state projection.

Available inventory is:

quantity_on_hand - quantity_reserved

The business logic for availability is handled by the backend service layer.

### Stock Movements

stock_movements is an immutable append-only historical ledger.

Allowed movement types:

- IN
- OUT

stock_movements must never be UPDATEd or DELETEd.

running_balance is a reporting snapshot and is NOT the authoritative current balance.

### Transfers

Transfers use:

- transactions
- transfer_records
- transfer_lines

In-transit stock must not distort warehouse stock reconciliation.

Partial receiving is supported.

Over-receiving must be prevented.

## Backend Status

Status:
- VERIFIED FOR ATOMIC TRANSACTION SERVICE, EXCEL IMPORT STAGING, TRIAL BALANCE & MOVEMENT REPORTS, AND PERIODIC PHYSICAL COUNT RECONCILIATION

Dependencies installed:

- fastapi
- uvicorn
- sqlalchemy
- asyncpg
- pydantic-settings
- python-jose
- httpx
- pytest
- pytest-asyncio
- openpyxl
- python-multipart

## Frontend Status

Status:
- VERIFIED CLEAN PRODUCTION BUILD (`npm run build`: 0 errors, 0 warnings, 1.82s build time)

Stack & Dependencies:
- React 19 + TypeScript + Vite 8
- Tailwind CSS 3.4 + PostCSS + Autoprefixer
- React Router DOM v7
- TanStack React Query v5
- Axios (with JWT interceptors)
- Supabase JS Client v2
- Lucide React icons
- Zod + React Hook Form + Hookform Resolvers
- clsx + tailwind-merge (`cn` utility)

Architecture & Aliases:
- `@/*` path alias mapped to `./src/*` across TypeScript and Vite
- `/api` dev proxy configured to forward to `http://127.0.0.1:8000`
- Clean environment variable configuration via `.env.example` and `.env`

## Current Task

Official Project Sites & Warehouse Bin Locations Management Configured. Seeded the client's official 13 project sites and warehouse bin locations into Supabase PostgreSQL, gracefully archived placeholder entities (`WH001`, `WH002`, `PRJ-KZ-01`), implemented repository and service filtering, and built dynamic administrative CRUD interfaces (`WarehousesPage` and `ProjectsPage`) wired into navigation and routes.

## Implemented This Cycle

- **Backend Authentication Subsystem**:
  - Created [`backend/app/schemas/auth.py`](backend/app/schemas/auth.py) & registered in [`backend/app/schemas/__init__.py`](backend/app/schemas/__init__.py): Defined `LoginRequest`, `DemoLoginRequest`, `UserAuthResponse`, and `TokenResponse`.
  - Added `create_access_token` utility to [`backend/app/security/auth.py`](backend/app/security/auth.py): Generates signed HS256 JWT tokens containing `sub`, `email`, `role`, and `exp` matching `settings.JWT_SECRET` and `settings.JWT_ALGORITHM`.
  - Created [`backend/app/api/routes/auth.py`](backend/app/api/routes/auth.py): Implemented `/api/v1/auth/token` for email/password authentication, `/api/v1/auth/demo-login` for instant role switching (`ADMIN`, `INVENTORY_MANAGER`, `STORE_KEEPER`, `VIEWER`), and protected `/api/v1/auth/me`.
  - Mounted router in [`backend/app/main.py`](backend/app/main.py) and registered in [`backend/app/api/routes/__init__.py`](backend/app/api/routes/__init__.py).
- **Frontend Interceptor & Login Flow Hardening**:
  - Hardened [`frontend/src/lib/api.ts`](frontend/src/lib/api.ts): Updated 401 response interceptor to log `console.error("API 401 Unauthorized:", error.config?.url)` and avoid redirecting if already on `/login` or during auth endpoint requests.
  - Updated [`frontend/src/features/auth/LoginPage.tsx`](frontend/src/features/auth/LoginPage.tsx): Replaced dummy mock tokens (`mock-jwt-token-*`) with live calls to `/auth/token` and `/auth/demo-login`. Added inline loading spinners and disabled states for demo role buttons.
- **Test Suite Expansion**:
  - Expanded [`backend/tests/test_auth.py`](backend/tests/test_auth.py) with 6 new tests covering demo account sign-in, unknown account rejection (401), all 4 role demo tokens, invalid role rejection (400), `/auth/me` profile retrieval, and verified that issued tokens authenticate against protected endpoints (`GET /api/v1/items`).

## Verification Evidence

- **Full Backend Test Suite**: `.\.venv\Scripts\pytest backend/tests`:
  - Exit Code: **0**
  - Result: **220 passed, 2 warnings in 4.19s** across all 15 test modules:
    * `test_auth.py`: 13 passed
    * `test_health.py`: 6 passed
    * `test_e2e_reconciliation.py`: 5 passed
    * `test_transactions.py`: 28 passed
    * `test_transfers.py`: 17 passed
    * `test_adjustments_and_srv.py`: 23 passed
    * `test_physical_count_reconciliation.py`: 13 passed
    * `test_reports.py`: 13 passed
    * `test_inventory.py`: 17 passed
    * `test_items.py`: 12 passed
    * `test_initial_stock_import.py`: 15 passed
    * `test_imports.py`: 27 passed
    * `test_warehouses.py`: 11 passed
    * `test_projects.py`: 10 passed
    * `test_categories.py`: 10 passed
- **Frontend Production Build**: `npm run build` executed in `frontend/`:
  - Exit Code: **0**
  - Errors: **0**
  - Warnings: **0**
  - Modules Transformed: **1,700**
  - Build Time: **1.82s**

## Comprehensive Production Readiness & Security Audit (2026-09-21)

A rigorous 5-step audit was executed across backend and frontend in accordance with `AGENTS.md`, `decisions.md`, `docs/SECURITY.md`, `docs/TRANSACTIONS.md`, and `docs/DATABASE.md`:

1. **Secrets & Frontend Hygiene Audit (docs/SECURITY.md)**:
   - **Secrets Scanning**: Full codebase scan confirmed `frontend/src/` contains zero server-side secrets (`SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`, or `JWT_SECRET`). Only `VITE_` prefixed public configuration keys (`VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`) are present.
   - **Error Masking & Traceback Sanitization**: Verified `backend/app/main.py` unhandled exception handler (`unhandled_exception_handler`) catches all unexpected exceptions, logs tracebacks server-side, and delivers sanitized HTTP 500 JSON (`{"detail": "An internal server error occurred. Please contact the system administrator."}`) to clients. Database schema names, connection strings, and SQL queries are completely masked. Verified by automated test `test_unhandled_exception_masks_internal_traceback`.

2. **Business Workflow & Concurrency Verification (docs/TRANSACTIONS.md, ADR-001 through ADR-006)**:
   - **Atomic PostgreSQL Transactions**: All 6 stock operations (`create_and_post_grv`, `create_and_post_siv`, `create_and_post_istv`, `create_and_post_istrv`, `create_and_post_srv`, `create_and_post_adjustment`) execute within atomic SQLAlchemy session blocks wrapped with automatic rollback on error.
   - **Deadlock Prevention**: `TransactionRepository.lock_inventory_balances_for_update` deterministically sorts item IDs and acquires row locks via `SELECT ... FOR UPDATE ORDER BY warehouse_id, item_id` in ascending order.
   - **Stock Availability Verification**: SIV and ISTV verify `available = quantity_on_hand - quantity_reserved >= requested_quantity` before creating any movements, rejecting over-requisition with HTTP 400.
   - **Over-Receiving Prevention (ADR-005)**: ISTRV verifies `line.quantity <= remaining_quantity (sent - received)` on the transfer record, strictly rejecting over-receipt with HTTP 400.
   - **Transfer Loop Prevention**: ISTV strictly rejects transactions where `source_warehouse_id == destination_warehouse_id` with HTTP 400.
   - **Return Audit Trail**: SRV strictly enforces that `reference_siv_id` points to an existing, POSTED SIV, and all returned items exist on the referenced voucher lines.
   - **Controlled Adjustments**: ADJUSTMENT enforces non-empty `adjustment_reason` (validated at both Pydantic schema and service levels) and blocks downward adjustments that would drop available stock below zero.

3. **Anti-Hardcoding Audit & Cleanup (AGENTS.md Rule 3 & Rule 4)**:
   - **Backend Services**: Verified 0 occurrences of `"WH001"` or `"Kazanchis"` in `backend/app/services/`. All warehouse and project entities resolve dynamically via UUIDs.
   - **Frontend Source**:
     * Removed obsolete scaffold file `frontend/src/features/inventory/InventoryPage.tsx` which contained static mock balances.
     * Cleaned up `frontend/src/features/dashboard/DashboardPage.tsx`: Removed fallback dummy rows that injected mock `"WH001"` records when queries were empty, replacing them with clean empty states ("No inventory items currently in transit across warehouses" / "No stock movements recorded yet").
     * Updated input placeholder in `frontend/src/features/reconciliation/ReconciliationPage.tsx` from `COUNT-20260919-WH001` to generic `COUNT-20260921-BATCH01`.
   - Result: 0 hardcoded warehouse codes or project names in operational code.

4. **Database Ledger Reconciliation Invariant (docs/DATABASE.md)**:
   - Executed live verification query against `vw_reconciliation_discrepancies` on Supabase PostgreSQL.
   - Result: **0 discrepancies** (`vw_reconciliation_discrepancies count: 0`).
   - Live Balances Audited:
     * `WH001` | `01-CM-00001` (Cement): On-Hand = 1,500.0000 | Ledger Total = 1,500.0000 (0.0000 diff)
     * `WH001` | `02-ST-00001` (Rebar 12mm): On-Hand = 500.0000 | Ledger Total = 500.0000 (0.0000 diff)
     * `WH001` | `02-ST-00002` (Rebar 16mm): On-Hand = 350.0000 | Ledger Total = 350.0000 (0.0000 diff)

5. **Automated Verification Suite Execution**:
   - **Backend Pytest**: `$env:PYTHONPATH = "backend"; .\.venv\Scripts\pytest backend/tests -v`
     * **211 passed, 0 failed** in 5.39s across 15 test suites.
   - **Frontend Production Build**: `npm run build`
     * Exit Code: **0**
     * Modules transformed: **1,696**
     * Zero TypeScript compilation errors, zero bundler errors.

## Final Production Readiness Assessment

- **Environment & Secrets Hygiene**: 100% Compliant (Zero committed secrets, strict `VITE_` segregation).
- **Network & Security Layer**: 100% Compliant (CORS, masked exception traces, Bearer JWT auth).
- **Transaction Concurrency & Invariants**: 100% Compliant (Deterministic locks, atomic dual-writes, negative stock protection).
- **Database & Ledger Consistency**: 100% Compliant (0 reconciliation discrepancies).
- **Anti-Hardcoding & Data Integrity**: 100% Compliant (Dynamic entity resolution, zero fake fallback data).
- **Test & Build Health**: 220/220 pytest passed, clean Vite production bundle.
- **Repository Deployment (2026-09-26)**:
  * Resolved OneDrive `cldflt.sys` "mmap failed" issue by mirroring clean repository to `C:\dev\inventory-management-system`.
  * Verified zero secret leaks with strict `.gitignore` rules.
  * Pushed to GitHub: `https://github.com/kirubelkidanu/inventory-management-system.git` (branch `main`).
- **Overall Status**: **FULLY PRODUCTION READY & DEPLOYED TO GITHUB**.

## Item Master Excel Import Modal Milestone (2026-09-27)

### What Was Implemented
1. **Backend Spreadsheet Processing & Route Aliasing**:
   - Enhanced `backend/app/services/import_.py` (`_detect_headers`, `_extract_row_data`) to parse client workbooks having columns `inventory id`, `description`, `main catagories`, `sub gatagory code`, and `unit measurment` without dictionary key collision.
   - Robust multi-strategy category matching across `category_str`, `sub_category`, `main_category`, and hyphen-split tokens against `categories_map`.
   - Automatic skipping of trailing blank draft rows (e.g. rows with both empty description and empty unit).
   - Flagging of missing units as `MISSING_UOM` to allow visual inspection in modal before committing.
   - Added endpoint routes in `backend/app/api/routes/imports.py`:
     * `POST /api/v1/imports/items/stage`: Uploads, validates, and returns `ImportBatchPreview` (batch metrics + errors list + valid items sample) in a single request.
     * `POST /api/v1/imports/items/{batch_id}/commit`: Aliased endpoint for atomic catalog ingestion.

2. **Frontend Import Modal & Interactive Validation Error Table**:
   - Defined interfaces in `frontend/src/types/index.ts`: `ImportBatch`, `ImportErrorItem`, `StagedItemSample`, `ImportBatchPreviewResponse`, and `CommitBatchResponse`.
   - Created React Query hooks in `frontend/src/features/inventory/useInventoryData.ts`: `useStageItemMaster`, `useCommitItemMaster` with automatic cache invalidation (`['items']`, `['inventory-balances']`).
   - Built `frontend/src/features/inventory/components/ImportItemsModal.tsx`:
     * Drag & drop / file picker accepting `.xlsx`, `.xls`, `.csv` with size checks and clear column guidelines.
     * Staging summary metrics: Total Rows, Valid Rows, Error Rows, Batch Reference.
     * Status alert banners (Green success banner if 0 errors; Amber banner if errors exist).
     * Interactive Validation Errors Table with live search, error code filtering (`UNKNOWN_CATEGORY`, `MISSING_CODE`, `MISSING_DESCRIPTION`, `MISSING_UOM`, `DUPLICATE_CODE`), raw value display, and descriptions.
     * Staged Valid Items Preview table showing item code, description, category, and UOM.
     * Atomic commit action button with loading spinners, error banners, and post-commit success confirmation card.
   - Integrated into `frontend/src/features/inventory/ItemsPage.tsx` with "+ Import from Excel" header button, modal wiring, and catalog refetch.
   - Re-exported component from `frontend/src/pages/ItemMasterPage.tsx` for routing flexibility.

### Files Changed
- `backend/app/services/import_.py`
- `backend/app/api/routes/imports.py`
- `backend/requirements.txt`
- `frontend/src/types/index.ts`
- `frontend/src/features/inventory/useInventoryData.ts`
- `frontend/src/features/inventory/components/ImportItemsModal.tsx`
- `frontend/src/features/inventory/ItemsPage.tsx`
- `frontend/src/pages/ItemMasterPage.tsx`
- `project_state.md`

### Tests & Verification Performed
- **Import Tests**: `pytest backend/tests/test_imports.py` -> **18 passed** in 0.48s (100% pass rate).
- **Full Backend Suite**: `pytest backend/tests` -> **211 passed** in 3.55s across 15 test suites.
- **Frontend Production Build**: `npm run build` (`tsc -b && vite build`) -> Exit Code 0, 1,697 modules transformed, zero TypeScript errors.
- **Mirrored Repository**: Synchronized cleanly to `C:\dev\inventory-management-system`.

## Production Bug Fix: React Error #310 & cPanel Bundle Packaging (2026-09-27)

### What Was Fixed & Implemented
1. **Unconditional Hook Execution (React Error #310)**:
   - Resolved the Rules of Hooks violation in `frontend/src/features/inventory/components/ImportItemsModal.tsx`.
   - Moved all hook invocations (`useAuth`, `useState`, `useRef`, `useStageItemMaster`, `useCommitItemMaster`, `useEffect`, and `useMemo`) to the unconditional top level of the component.
   - Removed early `if (!isOpen) return null;` previously located above the `useMemo` hooks, positioning it cleanly at the final JSX return level.
   - Guaranteed identical hook invocation count and order across both closed and open states.

2. **Quality Gates & Security Verification**:
   - `npm run build` (`tsc -b && vite build`) completed cleanly with 0 TypeScript/bundler errors (1,697 modules transformed).
   - `pytest backend/tests` executed with 211/211 tests passing without regression.
   - AGENTS.md Rule 6 verified: zero secrets or service keys in client code.

3. **cPanel Deployment Artifact**:
   - Generated `frontend/frontend-dist.tar.gz` containing the production `dist` bundle via native `tar -czf`.
   - Avoids ClamAV Foxhole ZIP heuristics on cPanel shared hosting and allows direct one-click extraction into `public_html`.

## Production Route Alignment & Render Dependency Fix (2026-10-31)

### What Was Fixed & Implemented
1. **Diagnosis of HTTP 404 on Excel Staging Route**:
   - Live probe of Render production backend (`https://api-inventory.moderngebeya.com/api/v1/openapi.json`) revealed that `/api/v1/imports/items/stage` was returning HTTP 404 because Render had failed to build/deploy recent commits due to `openpyxl>=3.1.2` and `python-multipart>=0.0.9` missing from `backend/requirements.txt`.
   - Render had stayed on a previous build that only had `/items/upload` and lacked `/items/stage`.

2. **Backend Route Registration & Trailing Slash Resiliency**:
   - Added `openpyxl>=3.1.2` and `python-multipart>=0.0.9` back to `backend/requirements.txt` to ensure Render build successfully installs dependencies and starts FastAPI.
   - Enhanced `backend/app/api/routes/imports.py`:
     * Added both trailing-slash and non-trailing-slash route handlers for `@router.post("/items/stage")` and `@router.post("/items/stage/")` to prevent any 307/404 redirects or proxy drops.
     * Added trailing slash handlers for commit endpoints (`/items/{batch_id}/commit`, `/items/{batch_id}/commit/`, `/batches/{batch_id}/commit`, `/batches/{batch_id}/commit/`) and batch preview endpoints (`/batches/{batch_id}`, `/batches/{batch_id}/`, `/items/{batch_id}`, `/items/{batch_id}/`).
     * Preserved existing `/items/upload` for full backward compatibility.

3. **Frontend Endpoint Verification**:
   - Confirmed `frontend/src/features/inventory/useInventoryData.ts` `useStageItemMaster` and `useCommitItemMaster` post to `/imports/items/stage` and `/imports/items/{batchId}/commit`, which perfectly aligns with the backend prefix `/api/v1/imports`.
   - Confirmed `multipart/form-data` file payload is bound to `file: UploadFile = File(...)`.

4. **Quality Gates & Tests**:
   - Backend tests: `pytest backend/tests/test_imports.py` (24 passed) and full suite `pytest backend/tests` (217 passed, 0 failed in 2.62s).
   - Frontend build: `npm.cmd run build` passed with 0 TypeScript/bundler errors (1,697 modules transformed).
   - Generated updated `frontend/frontend-dist.tar.gz` (181 KB) containing flat root distribution for cPanel deployment.

## Excel Staging Performance Optimization & Timeout Adjustment (2026-10-31)

### What Was Fixed & Implemented
1. **Frontend Timeout Extension**:
   - In `frontend/src/lib/api.ts`: Increased the default Axios client timeout from 30,000ms (30s) to 120,000ms (120s / 2 minutes) to provide plenty of headroom for enterprise multi-sheet file uploads and server-side validation.
   - In `frontend/src/features/inventory/useInventoryData.ts`: Explicitly configured `{ timeout: 120000 }` in `useStageItemMaster` and `useCommitItemMaster` requests.

2. **Backend Excel Ingestion Optimization**:
   - In `backend/app/services/import_.py` (`_parse_excel_rows` and `_parse_initial_stock_excel_rows`): Switched `openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)` wrapped in `try...finally: wb.close()`. This eliminates building the full in-memory cell DOM tree and leverages lazy XML stream iteration, drastically reducing memory usage and parsing latency on multi-sheet workbooks.
   - In `backend/app/services/import_.py` (`stage_item_master_file`): Pre-built an extensive in-memory category lookup dictionary (`fast_category_lookup`) indexed by uppercase codes, uppercase names, and hyphen-delimited token variations, reducing category lookups from nested searches to $O(1)$ constant time per row.
   - Deduplicated candidate item codes into a unique set before querying existing catalog codes in the database, minimizing SQL query length and index lookup overhead.

3. **Quality Gates & Tests**:
   - Backend tests: `pytest backend/tests/test_imports.py` (24 passed) and full test suite `pytest backend/tests` (217 passed, 0 failed in 3.64s).
   - Frontend build: `npm.cmd run build` passed with 0 TypeScript/bundler errors (1,697 modules transformed in 2.13s).
   - Generated updated `frontend/frontend-dist.tar.gz` (181 KB) containing flat root distribution for cPanel deployment.

## Partial Catalog Ingestion & Steel UOM Defaulting (2026-10-31)

### What Was Fixed & Implemented
1. **Corrupt/Draft Row Filtering (docs/PROJECT_SPEC.md Section 18 Note 4)**:
   - In `backend/app/services/import_.py`: Added filter during row iteration so that any row with empty description and empty unit (e.g., trailing anomaly `07-PC-D0159` in `PAINT AND CHEMICAL`) is automatically dropped as an empty/draft row without logging fatal validation errors.

2. **Steel UOM Auto-Defaulting (docs/PROJECT_SPEC.md Section 18 Note 1)**:
   - In `backend/app/services/import_.py`: Implemented auto-assignment of unit measurement `PCS` whenever `default_unit` is blank and the item's code starts with `02-ST-` or category is `STEEL` (or variations `02`, `02-ST`). This resolves the blank UOM issue across all 569 items in sheet `STEEL`.

3. **Graceful Handling of Existing Catalog Items**:
   - In `backend/app/services/import_.py` (`stage_item_master_file`): When an item code already exists in the catalog database, it is recorded with `error_code="ALREADY_EXISTS"` and skipped from `valid_items` and `staged_data["items"]`. It no longer prevents new items from being staged or committed.
   - Batch status is marked `VALIDATED` if all errors are non-fatal `ALREADY_EXISTS` skipped records and `valid_rows > 0`.

4. **Idempotent Atomic Catalog Commit**:
   - In `backend/app/services/import_.py` (`commit_item_master_import`): Queries the database for existing codes immediately before insert and filters them out. Rather than throwing HTTP 400 on collision, only genuinely new items are inserted into `items`, guaranteeing absolute idempotency.
   - Created alias `commit_item_master_batch = commit_item_master_import`.

5. **Frontend Modal UI & Metric Upgrades**:
   - In `frontend/src/features/inventory/components/ImportItemsModal.tsx`:
     - Added dedicated metric card for `Already in Catalog` (Amber, skipped from insert) alongside `New Valid SKUs` (Emerald, ready to commit), `Total Rows`, and `Validation Errors` (Rose, fatal errors).
     - Enhanced status banners to explain partial ingestion readiness and item counts.
     - Activated "Confirm & Commit {valid_rows} New Items" button whenever `valid_rows > 0`.
     - Added `ALREADY_EXISTS` amber badge styling in the validation issues table.

6. **Standard Categories Seeding**:
   - Expanded `SEED_CATEGORIES` in `backend/app/scripts/seed_demo_data.py` to include all 14 standard categories from `docs/PROJECT_SPEC.md` Section 2 (`01` through `14`). Executed script against live Supabase database, successfully verifying 14 active categories with 0 reconciliation discrepancies.

7. **Quality Gates & Tests**:
   - Backend tests: `pytest backend/tests/test_imports.py` (27 passed) and full test suite `pytest backend/tests` (220 passed, 0 failed in 2.99s).
   - Frontend build: `npm.cmd run build` passed with 0 TypeScript/bundler errors (1,697 modules transformed in 2.24s).
   - Re-packed production distribution: `frontend/frontend-dist.tar.gz` (182 KB).

## Official Project Sites & Warehouse Bin Locations Management (2026-10-31)

### What Was Fixed & Implemented
1. **Official 13 Client Sites & Warehouse Bin Locations**:
   - Configured the 13 authoritative project sites and linked warehouse bin locations per client requirements:
     * Kazanchis: Project Code `PRJ-KZ` ('Kazanchis Project') -> Warehouse `KZ-WH-001` ('Kazanchis Store / Bin 001')
     * Kality: Project Code `PRJ-KL` ('Kality Project') -> Warehouse `KL-WH-001` ('Kality Store / Bin 001')
     * Kaliti Garage: Project Code `PRJ-KL-GAR` ('Kaliti Garage') -> Warehouse `KL-WH-002` ('Kaliti Garage Store / Bin 002')
     * Goro ICT Park: Project Code `PRJ-GR` ('Goro ICT Park Project') -> Warehouse `GR-WH-001` ('Goro ICT Park Store / Bin 001')
     * Lamberet: Project Code `PRJ-LM` ('Lamberet Project') -> Warehouse `LM-WH-001` ('Lamberet Store / Bin 001')
     * Entoto: Project Code `PRJ-ET` ('Entoto Project') -> Warehouse `ET-WH-001` ('Entoto Store / Bin 001')
     * Jimma: Project Code `PRJ-JM` ('Jimma Project') -> Warehouse `JM-WH-001` ('Jimma Store / Bin 001')
     * Beshasha: Project Code `PRJ-BS` ('Beshasha Project') -> Warehouse `BS-WH-001` ('Beshasha Store / Bin 001')
     * Nekemt: Project Code `PRJ-NK` ('Nekemt Project') -> Warehouse `NK-WH-001` ('Nekemt Store / Bin 001')
     * Chaka: Project Code `PRJ-CK` ('Chaka Project') -> Warehouse `CK-WH-001` ('Chaka Store / Bin 001')
     * Jemo 3: Project Code `PRJ-JM3` ('Jemo 3 Project') -> Warehouse `JM3-WH-001` ('Jemo 3 Store / Bin 001')
     * Head Office: Project Code `PRJ-HO` ('Head Office') -> Warehouse `HO-WH-001` ('Head Office Store / Bin 001')
     * Ambo: Project Code `PRJ-AB` ('Ambo Project') -> Warehouse `AB-WH-0001` ('Ambo Store / Bin 0001')

2. **Placeholder Entity Deprecation & Ledger Invariant Preservation**:
   - Safely archived legacy demo entities `WH001` ('Central Logistics WH'), `WH002` ('Site Store WH002'), and `PRJ-KZ-01` ('Kazanchis Commercial Complex') by setting `is_active = FALSE` and prepending `[Archived]`.
   - Strictly preserved database ledger immutability (`prevent_movement_mutation` trigger) and historical integrity with 0 reconciliation discrepancies (`vw_reconciliation_discrepancies` == 0).

3. **Backend Repositories, Services & Routes**:
   - Created SQL migration `database/migrations/003_seed_official_sites_and_warehouses.sql` and seeding script `backend/app/scripts/seed_sites.py`.
   - Updated `WarehouseRepository` and `ProjectRepository` to support filtering by `is_active: bool | None = None`.
   - Updated `WarehouseService.list_warehouses` and `ProjectService.list_projects` with `is_active` parameter.
   - Enhanced `delete_warehouse` and `delete_project` with soft-deactivation fallback on `IntegrityError` to preserve historical foreign key links.
   - Exposed `is_active` query parameter in `GET /api/v1/warehouses` and `GET /api/v1/projects`.

4. **Frontend Dynamic Site & Warehouse Management**:
   - Added `location?: string | null` to `Project` interface in `frontend/src/types/index.ts`.
   - Created `frontend/src/features/sites/useSitesData.ts` React Query hooks for warehouses and projects CRUD and active toggling.
   - Built `frontend/src/features/sites/WarehousesPage.tsx`: Full enterprise table with search, status filtering, Add/Edit modal dialog, active toggling, and project assignment.
   - Built `frontend/src/features/sites/ProjectsPage.tsx`: Full enterprise table with search, status filtering, Add/Edit modal dialog, active toggling.
   - Connected routes in `frontend/src/App.tsx` (`/warehouses` and `/projects`).
   - Added 'Sites & Locations' navigation section to `frontend/src/layouts/AppLayout.tsx` and updated header pill from hardcoded placeholder to `13 Project Warehouses`.

5. **Quality Gates & Tests**:
   - Backend tests: `pytest backend/tests` (220 passed in 4.19s across 15 test suites).
   - Frontend build: `npm.cmd run build` passed with 0 TypeScript/bundler errors (1,700 modules transformed in 1.82s).
   - Re-packed production distribution: `frontend/frontend-dist.tar.gz` (182 KB).
   - Mirrored changes cleanly to `C:\dev\inventory-management-system` and pushed commit `cda84cc` to GitHub `origin main`.


---

## 2026-10-31 — Opening Balance (Initial Stock) Feature & 4-Column Excel Import with Unit Price Valuation

### 1. Database Migration & ORM Models
- **Migration 004**: Executed `database/migrations/004_add_unit_price_support.sql` adding `unit_price NUMERIC(15, 4) NULL CHECK (unit_price >= 0)` to `transaction_lines`.
- **ORM & Pydantic**: Updated `TransactionLine` model in `backend/app/models/transaction.py` and schemas in `backend/app/schemas/transaction.py` with optional `unit_price` and computed `total_price`. Added `OpeningBalanceLineCreate` and `OpeningBalanceCreate` schemas.

### 2. Backend Opening Balance Service & 4-Column Staging
- **Staging Service**: Implemented flexible 4-column staging (`inventory id`, `quantity`, `unit measurment`, `unit price`) in `backend/app/services/import_.py` via `POST /api/v1/imports/initial-stock/stage`.
  * Flexible header recognition across common variations.
  * Defaults blank UOM to item default unit in `items`.
  * Defaults blank `unit_price` to `0.0000`.
  * Detects and surfaces in-file duplicates (`DUPLICATE_IN_FILE`) and pre-existing warehouse balances (`ALREADY_EXISTS`).
- **Atomic Opening Balance Posting**: Built `create_and_post_opening_balance` in `backend/app/services/transaction.py` for both batch commit (`POST /api/v1/imports/initial-stock/{batch_id}/commit`) and manual submission (`POST /api/v1/transactions/opening-balance`).
  * Enforces atomic single-transaction execution per ADR-001, ADR-002, ADR-003, ADR-006, and ADR-009.
  * Header semantics: `transaction_type = 'ADJUSTMENT'`, `adjustment_reason = 'Opening Balance'`, `external_reference = 'OPENING_BALANCE'`.
  * Row locking: `SELECT ... FOR UPDATE` on `inventory_balances`.
  * Dual-write: updates `inventory_balances.quantity_on_hand` and appends immutable `stock_movements` (`movement_type = 'IN'`) with running balance calculation.
  * Emits `audit_logs` entry with `TRANSACTION_POSTED`.

### 3. Frontend Opening Balance Page
- **Route & Navigation**: Registered `/opening-balance` in `frontend/src/App.tsx` and added Opening Balance navigation link to `frontend/src/layouts/AppLayout.tsx` under INVENTORY & CATALOG.
- **Enterprise UI**: Built `frontend/src/features/inventory/OpeningBalancePage.tsx` with three tabs:
  * **Bulk Excel Import**: Target Warehouse selector, Effective Date, Excel template download, drag-and-drop file upload, staged preview metrics (Total Rows, Valid Rows, Skipped/Issues, Total Valuation), validation issues drawer, and Confirm and Post Opening Balance action.
  * **Manual Entry Form**: Warehouse/date selectors, dynamic line items with Item selector, unit price, quantity, real-time total price calculation, and direct posting.
  * **History**: View historical initial stock batches and posted opening balance transaction vouchers.

### 4. Verification & Quality Gates
- **Backend Tests**: `pytest backend/tests` passes 100% (**227 passed in 2.71s** across 16 test modules).
- **Ledger Invariant**: `vw_reconciliation_discrepancies` verified at 0 discrepancies on live Supabase PostgreSQL.
- **Frontend Build**: `npm.cmd run build` passes with 0 TypeScript/bundler errors (1,701 modules transformed).
- **Security Check**: Verified 0 secrets exposed in frontend code (AGENTS.md Rule 6).
- **Deployment Packaging**: Packaged `frontend/frontend-dist.tar.gz` (188 KB) for cPanel deployment.


---

## 2026-11-01 — Inventory Balances Direct Join Display Fix & Persistent Memory Unified

### 1. Root Cause & Display Resolution
- **Issue**: The Inventory Balances page was displaying SKU-UNKNOWN and Warehouse WH for balance records because useInventoryBalances relied on a client-side lookup against a paginated /items query (which failed when 5,646 catalog items were imported) and an active-only /warehouses query (which failed to match archived placeholder WH001).
- **Backend Direct Join Query**:
  * Rewrote InventoryRepository.list_balances and get_balance_by_item_warehouse in backend/app/repositories/inventory.py to perform direct SQL joins: inventory_balances JOIN items JOIN warehouses LEFT JOIN categories.
  * Added joined projection fields to InventoryBalanceRead schema: item_code, item_description, category_name, unit, warehouse_code, warehouse_name, warehouse_is_active, and computed available_quantity.
  * Added include_inactive_warehouses: bool = Query(False) parameter to GET /api/v1/inventory/balances and list_balances. By default, balances for archived/inactive warehouses (warehouse.is_active == false, such as legacy WH001) are excluded unless explicitly filtered by warehouse_id or include_inactive_warehouses=true.
- **Frontend Direct Rendering**:
  * Streamlined useInventoryBalances in frontend/src/features/inventory/useInventoryData.ts to directly consume backend response fields without issuing redundant secondary network requests for all catalog items.
  * Updated InventoryBalancesPage.tsx to render authentic joined fields directly.
  * Added an Include archived stores toggle and visual [Archived] badge for inactive store balances.

### 2. Persistent Project Memory Reconciled (AGENTS.md Compliance)
- Unified DECISIONS.md / decisions.md and PROJECT_STATE.md / project_state.md.
- Documented approved decisions ADR-001 through ADR-009 (including Opening Balance valuation and unit price support).
- Synchronized codebase and documentation between C:\dev\inventory-management-system and C:\Users\kirub\OneDrive\inventory-management-system.

### 3. Verification & Quality Gates
- **Backend Tests**: pytest backend/tests passes 100% (**229 passed in 2.72s** across 16 test modules).
- **Frontend Build**: npm run build passes with 0 TypeScript/bundler errors (1,701 modules transformed in 3.24s).
- **cPanel Artifact**: Packaged frontend/frontend-dist.tar.gz and copied to C:\Users\kirub\OneDrive\Desktop\OPENING-BALANCE-DIST.tar.gz (192 KB).

---

## 2026-11-01 — Frontend CI/CD Deployment Automation via GitHub Actions

### 1. Workflow Implementation
- **File**: .github/workflows/deploy-frontend.yml
- **Trigger**: Push to main branch when changes touch frontend/** or .github/workflows/deploy-frontend.yml, plus manual workflow_dispatch.
- **Build Environment**: ubuntu-latest with Node.js 20 (actions/setup-node@v4) and npm dependency caching.
- **Build Execution**: Runs npm ci and npm run build within frontend/ supplying VITE_API_URL and VITE_API_BASE_URL (https://api-inventory.moderngebeya.com/api/v1).
- **Deployment Action**: SamKirkland/FTP-Deploy-Action@v4.3.5 transferring ./frontend/dist/ directly to root ./ on the cPanel subdomain.
- **Server Routing Protection**: Excludes .htaccess, .well-known/**, and cgi-bin/** to guarantee Apache SPA URL rewrite rules, SSL certificates, and server scripts are never removed or overwritten.

### 2. Security Hygiene (AGENTS.md Rule 5 & docs/SECURITY.md)
- Zero secrets committed in code or workflow files.
- FTP credentials secured exclusively via GitHub repository secrets: ${{ secrets.FTP_SERVER }}, ${{ secrets.FTP_USERNAME }}, and ${{ secrets.FTP_PASSWORD }}.

---

## 2026-11-02 — Admin Single & Bulk Item Delete with Ledger-Safe Soft Archival (Option A)

### 1. Architectural Scope & Implementation
- **Strict Referential Integrity Enforcement (ADR-003 & DATABASE.md)**:
  * Inspected foreign key restrictions (ON DELETE RESTRICT) on items(id) across 	ransaction_lines, stock_movements, 	ransfer_lines, and inventory_balances.
  * Added ItemRepository.check_item_usage: checks counts of referencing lines in transactions, stock movements, and transfer lines, plus retrieves balance rows for non-zero stock (quantity_on_hand > 0 or quantity_reserved > 0).
  * **Unused Items**: If no transactions, movements, or transfers exist and inventory balances are zero (or absent), zero-quantity balances are deleted first, then the item is hard-deleted from items. An AuditLog entry with ction='DELETE', entity_type='item', entity_id=str(item.id), efore_state={...}, and change_summary='Hard-deleted unused item {item_code}' is recorded atomically. Outcome is DELETED.
  * **Used/Stocked Items**: If transactions, movements, transfers, or non-zero stock exist, hard-deletion is blocked. The item is soft-archived by setting is_active = False. An AuditLog entry with ction='UPDATE', efore_state={'is_active': True}, fter_state={'is_active': False}, and change_summary='Soft-archived item {item_code} with existing inventory history' is recorded atomically. Outcome is ARCHIVED.
- **API Endpoints & RBAC Authorization**:
  * DELETE /api/v1/items/{item_id}: Restricted to ADMIN role (
equire_roles('ADMIN')). Returns ItemDeleteResult. Non-admins receive 403 Forbidden.
  * POST /api/v1/items/bulk-delete: Restricted to ADMIN role. Takes ItemBulkDeleteRequest (item_ids: list[UUID]), executes atomic deletion/archival loop, and returns ItemBulkDeleteResult (deleted_count, rchived_count, 
esults).
  * PATCH /api/v1/items/{item_id}/restore: Restricted to ADMIN role. Restores is_active = True, records AuditLog action UPDATE, and returns updated ItemRead.
  * GET /api/v1/items: Supports include_inactive: bool = Query(False). By default, only active items (is_active == True) are returned.
- **Frontend Item Master Catalog Enhancements**:
  * Added ItemDeleteResult and ItemBulkDeleteResult models in rontend/src/types/index.ts.
  * Added useDeleteItem, useBulkDeleteItems, and useRestoreItem mutation hooks in rontend/src/features/inventory/useInventoryData.ts, with query invalidation for ['items'] and ['inventory-balances'].
  * Updated ItemsPage.tsx with admin-only table row checkboxes, 'Select all on page' header checkbox, floating bulk action bar ({count} items selected, 'Clear Selection', 'Delete / Archive Selected'), row-level Delete/Restore action buttons, 'Include archived items' toggle, dynamic feedback alert banner, and confirmation modal with enterprise warning text.
  * Re-exported ItemsPage from rontend/src/features/inventory/ItemMasterPage.tsx for route/module compatibility.

### 2. Quality Verification & Test Coverage
- **Backend Tests**: 236 passed in 3.54s across 16 test modules (19 passed in ackend/tests/test_items.py including unused hard-delete, used soft-archive, bulk delete, restore, include-inactive filter, role authorization 403 checks, and service unit tests).
- **Frontend Build**: 
pm run build completed with 0 errors (1,701 modules transformed in 6.82s).
- **Security Check**: Verified 0 secrets exposed (AGENTS.md Rule 5 & 6).

---

## 2026-11-02 — Goods Receiving Voucher (GRV) Unit Price & Auto-Calculated Total Price Implementation

### 1. Architectural Scope & Implementation
- **Backend Transaction Service**:
  * Updated TransactionService.create_and_post_grv in backend/app/services/transaction.py to persist line.unit_price directly onto transaction_lines.
  * If unit_price is omitted or None, defaults gracefully to Decimal("0.0000") preserving all existing transaction semantics and tests.
  * Invariant Protection: Dual-write ledger logic (ADR-001, ADR-002, ADR-003) remains strictly unchanged. Physical quantities update inventory_balances.quantity_on_hand and append IN stock movements to stock_movements.
  * TransactionLineRead computes total_price = (quantity * unit_price).quantize(Decimal("0.0001")) when unit_price is present.
- **Frontend GRV Entry Form & Transaction Details**:
  * Updated GRVPage.tsx with Unit Price (ETB) numeric input (min: 0, step: 0.01) and auto-calculated Total Price (ETB) read-only display column (quantity * unit_price).
  * Added real-time summary badge below the line items table displaying Total Voucher Value (ETB) and total received item units.
  * Updated VoucherSuccessCard.tsx to display Total Voucher Value for posted vouchers.
  * Updated TransactionsListPage.tsx modal detail view to render Unit Price (ETB), Total Price (ETB), and Total Voucher Value (ETB) for GRV vouchers and vouchers with unit prices.
  * Added TransactionDetailPage.tsx for dedicated voucher inspection and registered route /transactions/:id in App.tsx.
  * Updated useTransactionData.ts TransactionLineInput schema to accept optional unit_price?: number | null.

### 2. Verification & Quality Gates
- **Backend Tests**: 238 passed in 4.88s across 16 test modules (30 passed in test_transactions.py including API-level and service-level GRV unit price persistence and computed total price).
- **Frontend Build**: npm run build completed with 0 errors (1,702 modules transformed in 5.04s).
- **Security Check**: Verified 0 secrets exposed (AGENTS.md Rule 5 & 6).

---

## 2026-11-02 — Manual Item Maintenance with Create, Edit, Safe Delete, and Audit Logging

### 1. Architectural Scope & Implementation
- **Strict Role-Based Access Control (RBAC)**:
  * `POST /api/v1/items`: Restricted to `ADMIN` and `INVENTORY_MANAGER`. Enforces non-empty strings and case-insensitive uniqueness check on `item_code`. Records an `AuditLog` entry (`action='CREATE'`, `entity_type='item'`, `entity_id=str(item.id)`, `change_summary='Created item {item_code}'`). Non-authorized roles (`VIEWER`, `STORE_KEEPER`) receive HTTP 403 Forbidden.
  * `PUT /api/v1/items/{item_id}`: Restricted to `ADMIN` and `INVENTORY_MANAGER`. Allows updating `description`, `category_id`, `default_unit`, and `is_active`. SKU `item_code` remains strictly immutable to protect ledger referential integrity. Records an `AuditLog` entry (`action='UPDATE'`, `entity_type='item'`, with full `before_state` and `after_state`). Non-authorized roles receive HTTP 403 Forbidden.
  * `DELETE /api/v1/items/{item_id}` & `POST /api/v1/items/bulk-delete`: Restricted to `ADMIN` with referential integrity protection (hard-deletes unused items with 0 balances; soft-archives items with inventory or transaction history).
  * `GET /api/v1/items`: Accessible to all authenticated users. Enhanced with query filters: `search`, `category_id`, `include_inactive`, `skip`, and `limit`. Returns `X-Total-Count` header.
- **CORS Expose Headers**:
  * Updated `CORSMiddleware` in `backend/app/main.py` to include `expose_headers=["*", "X-Total-Count"]`, allowing browser frontend clients to access pagination totals.
- **Frontend Item Maintenance Screen (`/items`)**:
  * Added "+ Add New Item" button in `ItemsPage.tsx` header, visible to `ADMIN` and `INVENTORY_MANAGER`.
  * Added "Add New Item" modal with fields: Item Code (SKU), Description, Category dropdown, Default Unit of Measure with quick-fill chips (`PCS`, `KG`, `BAG`, `M2`, `M3`, `ROLL`, `SET`, `LTR`), and Active status toggle.
  * Added "Edit Item Master" modal triggered by a per-row pencil button (visible to `ADMIN` and `INVENTORY_MANAGER`), with immutable SKU display, editable description, category, default unit chips, and active toggle.
  * Connected server-side search, category filter, and pagination via `useItems`, `useCreateItem`, and `useUpdateItem` mutation hooks with TanStack Query cache invalidation for `['items']` and `['inventory-balances']`.
- **Database & Stock Invariants**:
  * Dual-write ledger logic (`ADR-001`, `ADR-002`, `ADR-003`) remains completely untouched. Item maintenance does not modify stock balances directly; all stock changes strictly flow through `TransactionService`.

### 2. Verification & Quality Gates
- **Backend Tests**: 244 passed in 3.58s across 16 test modules (25 passed in `backend/tests/test_items.py` including manual item creation, case-insensitive duplicate rejection, updating item fields, audit logging, server-side search and pagination, and 403 authorization checks for `VIEWER`).
- **Frontend Build**: `npm run build` (`tsc -b && vite build`) completed with 0 errors (1,702 modules transformed).
- **Security Check**: Verified 0 exposed credentials or secrets (AGENTS.md Rule 5 & 6).

---

## 2026-11-02 — High-Performance Async Searchable Item Combobox for Transactions (GRV, SIV, ISTV, ISTRV, SRV, Adjustment)

### 1. Architectural Scope & Implementation
- **Searchable Item Combobox (`frontend/src/components/ItemCombobox.tsx`)**:
  * Implemented reusable async combobox replacing static HTML `<select>` with 1,000+ un-indexed options across all transaction line tables.
  * Instant debounced text typing (~250ms) querying `GET /api/v1/items?search={query}&page_size=50&is_active=true` leveraging GIN trigram index on `description` and B-tree index on `item_code`.
  * Initial catalog presentation: when opened without a search query, displays the first 50 active items for immediate browsing and scroll selection.
  * Selected item persistence: integrates a single-item detail query (`useQuery(['item-detail', value])`) ensuring that items already selected on a voucher always display their exact SKU badge (`[01-CM-00001]`), full description, and UOM even when outside the current 50 search results.
  * Visual status & empty states: provides a loading spinner during debounced network fetches, clear "No items found matching '{query}'" empty state, keyboard navigation (`ArrowUp`, `ArrowDown`, `Enter`, `Escape`), and outside-click auto-close.
  * Visual duplicate prevention (`ADR-006`): `excludeItemIds` prop visually disables and tags items already added to other lines on the same voucher (`Already added`), preventing client submission errors before validation triggers.
  * UOM auto-population: on item selection, passes both `itemId` and the complete `item` object so transaction forms automatically populate `unit` with `item.default_unit`.
- **Backend API Synonyms (`backend/app/api/routes/items.py`)**:
  * Enhanced `GET /api/v1/items` to support parameter synonyms: `page_size` (alias for `limit`) and `is_active: bool | None` (synonym for `include_inactive = not is_active`), preserving complete backward compatibility with all prior callers.
- **Transaction Line Tables Updated**:
  * `GRVPage.tsx`: Replaced static SKU dropdown with `ItemCombobox`, retaining `Unit Price (ETB)`, auto-calculated `Total Price (ETB)`, total voucher value summary, and `ADR-006` validation.
  * `SIVPage.tsx`: Replaced static SKU dropdown with `ItemCombobox`.
  * `ISTVPage.tsx`: Replaced static SKU dropdown with `ItemCombobox`.
  * `ISTRVPage.tsx`: Replaced static SKU dropdown with `ItemCombobox`.
  * `SRVPage.tsx`: Replaced static SKU dropdown with `ItemCombobox`.
  * `AdjustmentPage.tsx`: Replaced static SKU dropdown with `ItemCombobox`.

### 2. Verification & Quality Gates
- **Backend Tests**: 244 passed in 3.43s across 16 test modules (including 25 tests in `test_items.py` verifying combobox query patterns `search`, `page_size`, and `is_active=true`).
- **Frontend Build**: `npm run build` (`tsc -b && vite build`) passed with 0 errors (1,703 modules transformed).
- **Security Check**: Verified 0 exposed credentials or secrets (AGENTS.md Rule 5 & 6).

---

## 2026-11-02 — Unit Price (ETB) and Total Valuation (ETB) in Trial Balance Ledger and Excel Export

### 1. Architectural Scope & Implementation
- **Backend Schema & Service (`backend/app/schemas/report.py`, `backend/app/services/report.py`, `backend/app/repositories/report.py`)**:
  * Extended `TrialBalanceItem` with `unit_price: Optional[Decimal] = None` and `total_price: Optional[Decimal] = None`.
  * Extended `TrialBalanceResponse` with `total_valuation: Optional[Decimal] = None`.
  * Updated `ReportRepository.get_trial_balance` and `get_all_trial_balance_movements` queries to select `TransactionLine.unit_price`. Maintained the exact 4-tuple return signature `(rows, total_count, total_in, total_out)` for backward compatibility with existing tests.
  * In `ReportService._map_trial_balance_item`, extracted `unit_price` quantized to 4 decimal places and auto-computed `total_price = unit_price * quantity` (or `None` when unit price is unrecorded).
  * In `ReportService.get_trial_balance_report`, computed `total_valuation = sum(item.total_price for item in items if item.total_price is not None)`.
  * In `ReportService.export_trial_balance_excel`:
    * Expanded headers from 18 to 20 columns by inserting "Unit Price (ETB)" (col 17) and "Total Value (ETB)" (col 18).
    * Updated title and metadata banner merges from `A1:R1` and `A2:R2` to `A1:T1` and `A2:T2`.
    * Formatted numeric columns 17 and 18 with currency format `#,##0.00`.
    * Extended total row with cumulative valuation sum `sum_val` in column 18 and adjusted merged summary label `A{total_row}:M{total_row}`.
- **Frontend Types & UI (`frontend/src/types/index.ts`, `frontend/src/features/reports/TrialBalancePage.tsx`)**:
  * Added `unit_price` and `total_price` to `TrialBalanceItem`, and `total_valuation` to `TrialBalanceResponse`.
  * Added a 4th summary stat card to `TrialBalancePage.tsx` displaying `Movement Valuation (ETB)` formatted to 2 decimal places with `Banknote` icon.
  * Added "Unit Price (ETB)" and "Total Value (ETB)" columns to the authoritative ledger table, formatting positive numbers as currency or "—" when blank.
  * Updated loading and empty state table `colSpan` from 12 to 14.
  * Enhanced the Transaction Inspection modal line items table to show "Unit Price (ETB)" and "Total Price (ETB)" alongside item SKU descriptions.
- **Data Integrity & Ledger Invariants**:
  * Stock immutability trigger `trg_protect_stock_movements` and `vw_reconciliation_discrepancies` remain completely untouched (0 discrepancies).
  * No database migrations were needed as `unit_price` already resides in `transaction_lines` (migration 004).

### 2. Verification & Quality Gates
- **Backend Tests**: 244 passed in 3.54s across 16 test modules (including updated `test_reports.py` validating unit price and valuation in report mapping, Excel columns, and totals).
- **Frontend Build**: `npm run build` (`tsc -b && vite build`) passed with 0 errors (1,703 modules transformed).
- **Security Check**: Verified 0 exposed credentials or secrets (AGENTS.md Rule 5 & 6).


---

## 2026-11-03 — Dynamic Header Row & Multi-Sheet Detection for Opening Balance Excel Ingestion

### 1. Architectural Scope & Implementation
- **Dynamic Header & Worksheet Ingestion (`backend/app/services/import_.py`)**:
  * Resolved the "The uploaded file contains no data rows" failure when staging multi-sheet workbooks or files with title banners / headerless data like `kality p2 begi.xlsx`.
  * **Worksheet Traversal**: Prioritizes `wb.active` then iterates all sheets in `wb.worksheets`, skipping blank or informational cover sheets and extracting stock balances from sheets containing actual stock columns.
  * **Dynamic Header Finder**: Scans rows 1 through 15 looking for canonical item identifier (`inventory id`, `item code`, `sku`, `code`, `item`) AND quantity (`quantity`, `qty`, `count`, `balance`, `stock`, `opening balance`) columns, gracefully skipping title banners, dates, and store metadata rows above the table header.
  * **Headerless 4-Column Auto-Detection**: If no header row is found in rows 1-15, detects raw 4-column opening inventory spreadsheets (`[item_code, quantity, unit, unit_price]`) where the first non-empty row has an item identifier in col 0 and positive numeric quantity in col 1, allowing direct ingestion of client spreadsheets like `kality p2 begi.xlsx`.
  * **Summary & Signature Row Filtering**: Implemented `_is_summary_or_signature()` to automatically skip empty spacer rows and trailing summary/signature rows (`Total`, `Grand Total`, `Approved by`, `Prepared by`, `Checked by`, etc.) to prevent false catalog item errors.
  * **Data Normalization**: Correctly converts numeric item IDs (e.g. `101`, `101.0`) to canonical string SKUs, handles decimal/integer quantities, UOM normalization, and optional unit prices.

### 2. Verification & Quality Gates
- **Backend Tests**: 244 passed in 3.00s across 16 test modules. Added comprehensive test coverage in `backend/tests/test_imports.py`:
  * `test_stage_initial_stock_with_title_rows_above_header`: Verifies titles on rows 1-4, headers on row 5, and summary/signature row skipping.
  * `test_stage_initial_stock_non_first_sheet`: Verifies multi-sheet workbook where data is on a non-first sheet.
  * `test_stage_initial_stock_4_column_valid_and_error_rows`: Verifies 4-column format where valid items go to staged rows and invalid items/quantities log to `import_errors`.
  * `test_stage_initial_stock_headerless_4_column_format`: Verifies raw 4-column file without header row (e.g. `kality p2 begi.xlsx`).
- **Real File Validation**: Verified against client files `kality p2 begi.xlsx` (33/33 rows parsed) and `kality p2 begi (2).xlsx` (33/33 rows parsed).
- **Frontend Build**: `npm run build` (`tsc -b && vite build`) passed with 0 errors (1,703 modules transformed).
- **Security Check**: Verified 0 exposed credentials or secrets (AGENTS.md Rule 5 & 6).


---

## 2026-11-03 — Fix Opening Balance Network Error on Commit & Direct Link to Trial Balance Ledger

### 1. Architectural Scope & Implementation
- **Resolved Network / CORS Errors on Commit (`backend/app/api/routes/`)**:
  * Root caused the Network Error during "Confirm & Post Opening Balance" and manual entry:
    1. Attribute expiration on commit: `TransactionService.create_and_post_opening_balance` committed the database session without eagerly reloading lines, causing an internal `MissingGreenlet` exception during FastAPI response serialization to `TransactionRead`. Added `refreshed = await self.repo.get_transaction_by_id(tx_id)` before returning.
    2. Import commit pre-commit capture: In `ImportService.commit_initial_stock_import`, pre-captured `batch_id`, `batch_number`, and `transaction_numbers` prior to session commit to avoid expired attribute lookups.
    3. Route trailing slash & path aliases: Fixed route declarations across `imports.py` and `inventory.py` to support with/without trailing slashes and multiple path aliases (`/initial-stock/{batch_id}/commit`, `/initial-stock/commit/{batch_id}`, `/batches/{batch_id}/commit`, `/{batch_id}/commit`, `/opening-balance`, `/opening-balance/`) preventing 307 temporary redirect CORS/Network errors.
- **Trial Balance Ledger Linkage (`backend/app/repositories/report.py`)**:
  * Converted `User` join from inner join to `outerjoin(User, Transaction.created_by == User.id)` across both `get_trial_balance` and `get_all_trial_balance_movements`.
  * Guarantees that opening balance adjustments (`transaction_type='ADJUSTMENT'`, `external_reference='OPENING_BALANCE'`) and initial stock vouchers are consistently displayed in the Trial Balance ledger under their respective warehouse, item SKU, positive IN quantity, unit price, and valuation.
- **Frontend Error Handling & Query Invalidation (`frontend/src/features/inventory/`, `frontend/src/features/transactions/`)**:
  * Enhanced `extractErrorMessage` to extract `error.response?.data?.detail`, array validation errors, and meaningful network error messages rather than raw browser exceptions.
  * Added query invalidations for `['trial-balance']` and `['transactions']` upon successful initial stock commit and manual entry posting.
  * Added direct "View in Trial Balance" action buttons on both Excel batch commit and manual entry success screens.

### 2. Verification & Quality Gates
- **Backend Tests**: 248 passed in 4.34s across 16 test modules (all opening balance and import commit tests passing 100%).
- **Frontend Build**: `npm run build` (`tsc -b && vite build`) passed with 0 errors (1,703 modules transformed).
- **Ledger Discrepancies**: Verified `vw_reconciliation_discrepancies` remains at 0 discrepancies.
- **Security Check**: Verified 0 exposed credentials or secrets (AGENTS.md Rule 5 & 6).

---

## 2026-11-03 — CORS Hardening, Exception Header Preservation, and Double-Slash Prevention on Opening Balance

### 1. Architectural Scope & Implementation
- **CORS Hardening & Allowed Origins (`backend/app/core/config.py`, `backend/app/main.py`)**:
  * Added `https://inventory.moderngebeya.com` and `http://inventory.moderngebeya.com` directly into the default `CORS_ORIGINS` in `Settings`.
  * Added support for `BACKEND_CORS_ORIGINS` and `ALLOWED_ORIGINS` environment variables, aggregating all origin sources into a normalized, clean, deduplicated `cors_origins_list` with trailing slashes stripped.
  * Configured `CORSMiddleware` with `allow_origins=settings.cors_origins_list`, `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`, and `expose_headers=["*", "X-Total-Count"]`.
  * Updated `unhandled_exception_handler` in `main.py` to dynamically attach CORS response headers (`Access-Control-Allow-Origin`, `Access-Control-Allow-Credentials`, `Access-Control-Allow-Methods`, `Access-Control-Allow-Headers`) whenever an incoming request carries an allowed `Origin` header. This prevents the browser from masking 4xx/5xx exceptions as opaque "Network Error: Failed to reach the server. Please check your connection or CORS configuration".
- **Opening Balance Endpoint Hardening (`backend/app/api/routes/`)**:
  * Corrected Python syntax in `backend/app/api/routes/inventory.py` ensuring `from __future__ import annotations` is the initial statement.
  * Added `try ... except ValueError as e: raise HTTPException(status_code=400, detail=str(e))` and catch-all `HTTPException` error wrappers across `imports.py` (`commit_batch`, `commit_initial_stock_batch`), `inventory.py` (`create_inventory_opening_balance`), and `transactions.py` (`create_opening_balance`).
  * Ensured both `/opening-balance` and `/opening-balance/` decorators are registered on the FastAPI routers to prevent Starlette 307 Temporary Redirects.
  * In `TransactionService.create_and_post_opening_balance`, added safe type checking for `refreshed` (`isinstance(refreshed, Transaction)`) so both mock testing and live database transactions return a valid `Transaction` model.
- **Frontend URL Normalization & Query Invalidation (`frontend/src/lib/api.ts`, `frontend/src/features/inventory/useInventoryData.ts`)**:
  * Stripped trailing slashes from `API_BASE_URL` in `frontend/src/lib/api.ts` to prevent unintentional double slashes (`//opening-balance`).
  * Added request interceptor rule in `api.ts` replacing leading double-slashes (`^//+`) with a single `/`.
  * Updated `useCommitInitialStock` and `useCreateManualOpeningBalance` mutation hooks to invalidate `['inventory-balances']`, `['trial-balance']`, `['transactions']`, `['import-batches']`, `['initial-stock-batches']`, and `['opening-balance-transactions']`.
- **Automated Test Coverage (`backend/tests/test_opening_balance.py`)**:
  * Added `test_cors_preflight_and_origin_headers`: Verifies preflight OPTIONS and response CORS headers for `https://inventory.moderngebeya.com` and `http://localhost:5173`.
  * Added `test_opening_balance_no_307_redirect_with_trailing_slash`: Verifies both `/api/v1/transactions/opening-balance` and `/api/v1/transactions/opening-balance/` return 201 with correct CORS headers and no 307 temporary redirects.

### 2. Verification & Quality Gates
- **Backend Tests**: 250 passed in 3.59s across 16 test modules (100% passing).
- **Frontend Build**: `npm run build` (`tsc -b && vite build`) passed with 0 errors (1,703 modules transformed).
- **Security Check**: Verified 0 exposed credentials or secrets (AGENTS.md Rule 5 & 6).

---

## 2026-11-03 — Fix CheckViolationError on audit_logs_action_check for Opening Balance

### 1. Architectural Scope & Implementation
- **Audit Log Constraint Compliance (`backend/app/services/transaction.py`)**:
  * In `TransactionService.create_and_post_opening_balance`, replaced `action="TRANSACTION_POSTED"` and `entity_type="transactions"` with `action="POST"` and `entity_type="transaction"`.
  * Fully adheres to `docs/DATABASE.md` Section 2.12 and migration check constraint `audit_logs_action_check` (`CHECK (action IN ('CREATE', 'UPDATE', 'POST', 'CANCEL', 'CORRECT', 'IMPORT', 'DELETE'))`).
  * Eliminates the `CheckViolationError` thrown when PostgreSQL attempts to insert an audit log with an invalid action verb on opening balance vouchers.
- **Audit Verification & Test Coverage (`backend/tests/`)**:
  * Updated `backend/tests/test_opening_balance.py` to assert `audit_call["action"] == "POST"`, `entity_type == "transaction"`, and `entity_id == str(tx.id)`.
  * Added `test_opening_balance_audit_log_satisfies_check_constraint` in `backend/tests/test_transactions.py` asserting that opening balance creation emits an audit log conforming to the valid action set.
  * Added `test_initial_stock_commit_audit_log_actions_satisfy_check_constraint` in `backend/tests/test_imports.py` asserting that bulk initial stock commit writes `action="IMPORT"` for the batch and delegates to opening balance posting with `action="POST"`.

### 2. Verification & Quality Gates
- **Backend Tests**: 252 passed in 3.87s across 16 test modules (100% passing).
- **Frontend Build**: `npm run build` (`tsc -b && vite build`) passed with 0 errors (1,703 modules transformed).
- **Security Check**: Verified 0 exposed credentials or secrets (AGENTS.md Rule 5 & 6).


---

## 2026-11-03 — Automatic Unit Price Lookup, Total Price Calculation & Trial Balance Valuation for SIV

### 1. Architectural Scope & Implementation
- **Data Models & Schemas (`backend/app/schemas/item.py`, `backend/app/schemas/transaction.py`)**:
  * Added `latest_unit_price: Optional[Decimal] = None` to `ItemRead`.
  * Added `ItemLatestCostResponse(item_id, latest_unit_price, warehouse_id)` schema.
  * Preserved `TransactionLineCreate.unit_price` and auto-computed `TransactionLineRead.total_price` (`quantity * unit_price`).
- **Inbound Cost Lookup & Transaction Service (`backend/app/repositories/`, `backend/app/services/`)**:
  * Implemented `get_latest_inbound_unit_price(item_id, warehouse_id)` and batch `get_latest_inbound_unit_prices_batch(item_ids)` in `TransactionRepository` and `ItemRepository`.
  * Queries the latest unit price from POSTED inbound transactions (`GRV` or `ADJUSTMENT` with `OPENING_BALANCE` external reference).
  * In `TransactionService.create_and_post_siv`, lines with no explicitly specified `unit_price` automatically retrieve and save the latest inbound unit price to `transaction_lines.unit_price`.
  * Preserved stock decrement invariants: SIV strictly decrements `inventory_balances.quantity_on_hand` and writes `movement_type='OUT'` with `signed_quantity = -quantity`.
- **API Endpoints (`backend/app/api/routes/items.py`)**:
  * Updated `list_items` to batch-resolve `latest_unit_price` across items.
  * Updated `get_item` to resolve and return `latest_unit_price`.
  * Added `GET /api/v1/items/{item_id}/latest-cost` (and trailing slash variant) for fast single-item pricing lookups.
- **Frontend SIV Form & Transaction Detail (`frontend/src/features/transactions/`)**:
  * `SIVPage.tsx`: Added `Unit Price (ETB)` editable input and auto-calculated `Total Price (ETB)` column to SIV voucher creation.
  * Selecting an item via `ItemCombobox` automatically populates `unit_price` from `item.latest_unit_price` or via `/latest-cost`, falling back cleanly to `0.00`.
  * Added voucher summary footer displaying `Total Issued Quantity` and `Total Issued Valuation (ETB)`.
  * `TransactionDetailPage.tsx`: Extended unit price and total price display to SIV transactions alongside GRVs.
  * Trial Balance ledger and Excel export automatically display unit price and total valuation for SIV lines via existing `transaction_lines.unit_price` joins.

### 2. Verification & Quality Gates
- **Backend Tests**: 254 passed in 3.55s across 16 test modules (100% passing).
  * Added `test_service_siv_persists_unit_price_and_computes_total_valuation` in `backend/tests/test_transactions.py`.
  * Added `test_service_siv_auto_looks_up_latest_inbound_unit_price_when_none` in `backend/tests/test_transactions.py`.
- **Frontend Build**: `npm run build` (`tsc -b && vite build`) passed with 0 errors (1,703 modules transformed).
- **Stock Invariant Verification**: All stock deductions, movements, and reconciliation checks remain 100% in balance.
- **Security Check**: Verified 0 exposed credentials or secrets (AGENTS.md Rule 5 & 6).


---

## 2026-11-03 — Opening Balance Canonical UOM Auto-Mapping & Duplicate SKU Merging (ADR-006 Compliance)

### 1. Architectural Scope & Implementation
- **Canonical UOM Synonym Auto-Mapping (`backend/app/services/import_.py`)**:
  * Implemented `UOM_SYNONYM_GROUPS` and `UOM_SYNONYM_LOOKUP` covering Volume (`ltr`, `liter`, `litre`, etc.), Count (`pcs`, `pc`, `piece`, `pieces`, `ea`, `each`, `no`), Weight (`kg`, `kgs`, `kilogram`), Area (`m2`, `sqm`, `m^2`), Length (`m`, `mtr`, `meter`), Packaging (`bag`, `roll`, `pkt`), and Mass (`qtl`, `quintal`).
  * Created `resolve_canonical_uom(raw_uom, item_default_unit)` strictly following rules:
    - Rule a: If raw cell UOM is blank or whitespace, default safely to `item.default_unit`.
    - Rule b: Case-insensitive matching accepts equivalent case (e.g., `kg` matches `KG`).
    - Rule c: Synonym group mapping maps synonym variants to `item.default_unit` (e.g., `ltr` matches `Liter`, `pcs` matches `Pcs`).
    - Rule d: True dimensional conflicts (e.g., `KG` vs `Pkt`) log `INVALID_UOM` in `import_errors`.
- **Duplicate SKU Aggregation & Merging per ADR-006 (`backend/app/services/import_.py`)**:
  * Removed row-level rejection on in-file duplicate SKUs (`DUPLICATE_IN_FILE` / `DUPLICATE_ENTRY`).
  * After initial validation, grouped all valid row candidates by `(warehouse_id, item_id)`:
    - Sums total line quantity: `total_qty = sum(quantities)`.
    - Computes weighted average unit price: `sum(qty * price) / sum(qty)` when multiple rows have prices; retains single price if only one row provides a price; defaults to `0.0000` if omitted.
    - Sets `is_merged = True`, `merged_count = N`, `merged_rows = [row_numbers]`, and `merge_note = f"Merged {N} rows (rows: #r1, #r2) with total quantity {total_qty}"`.
  * Guarantees that `staged_data["rows"]` outputs exactly one line per item/warehouse, strictly fulfilling database constraint `UNIQUE(transaction_id, item_id)` (ADR-006) during atomic opening balance posting.
- **Frontend Staging Preview Alignment (`frontend/src/features/inventory/OpeningBalancePage.tsx`, `frontend/src/types/index.ts`)**:
  * Extended `InitialStockStagedRow` interface with `is_merged`, `merged_count`, `merged_rows`, and `merge_note`.
  * Updated "Valid Stock Lines" table to display `Merged (N rows)` badge with tooltip indicating source spreadsheet row numbers, and display `#{row_number}*` row indicator.
  * Preserved canonical UOM display resolving to `item.default_unit`.

### 2. Verification & Quality Gates
- **Backend Tests**: 259 passed in 4.53s across 16 test modules (100% passing).
  * Added `test_stage_initial_stock_uom_case_insensitive_match` in `backend/tests/test_imports.py`.
  * Added `test_stage_initial_stock_uom_synonyms_mapping` in `backend/tests/test_imports.py`.
  * Added `test_stage_initial_stock_blank_uom_falls_back_to_default_unit` in `backend/tests/test_imports.py`.
  * Added `test_stage_initial_stock_dimensional_mismatch_logs_invalid_uom` in `backend/tests/test_imports.py`.
  * Added `test_stage_initial_stock_merges_duplicate_skus_and_calculates_weighted_price` in `backend/tests/test_imports.py`.
  * Updated `backend/tests/test_initial_stock_import.py` and `backend/tests/test_opening_balance.py` to assert duplicate row merging behavior.
- **Frontend Build**: `npm run build` (`tsc -b && vite build`) passed with 0 errors (1,703 modules transformed).
- **Ledger Invariants**: Stock transactions, dual writes, and `vw_reconciliation_discrepancies` remain 100% in balance.
- **Security Check**: Verified 0 exposed credentials or secrets (AGENTS.md Rule 5 & 6).


---

## 2026-11-04 — Opening Balance Resilient SKU Formatting Normalization & Controlled UOM Catalog Fallback

### 1. Architectural Scope & Implementation
- **Resilient SKU Formatting Normalization (`backend/app/services/import_.py`, `backend/app/repositories/import_.py`)**:
  * In `ImportRepository.get_items_by_codes` and `stage_initial_stock_file`, candidate SKU codes automatically expand to include standard hyphenated permutations (`XX-YY-ZZZZZ`) for any 9-character alphanumeric sequence.
  * Pre-indexed catalog items into dual dictionaries:
    - Exact key: `item.item_code.strip().upper()`
    - Normalized alphanumeric key: `re.sub(r'[^A-Z0-9]', '', item.item_code.upper())`
  * In the row validation loop, raw codes (e.g. `'11-OT -00106'`, `'11 OT 00256'`, `'05 TL-00022'`) first attempt exact lookup and fall back to alphanumeric matching, automatically populating the canonical catalog SKU code while marking `sku_normalized = True` and recording `original_item_code`.
  * Truly non-existent codes (e.g. `'17-CL-00014'`) continue to log `INVALID_ITEM` in `import_errors`.
- **Controlled UOM Catalog Fallback Mode & Synonym Expansion (`backend/app/services/import_.py`)**:
  * Added `pail`, `pails`, `gallon`, `gallons`, and `gal` to the Volume synonym group, mapping directly to `Liter` or `Gallon` without error.
  * Implemented `fallback_to_catalog_uom: bool = False` parameter in `stage_initial_stock_file` (with `fallback_to_catalog_uom: bool = Form(True)` in FastAPI route).
  * When `fallback_to_catalog_uom=True` and a dimensional mismatch occurs (e.g. `roll` vs `PCS`), the staged line adopts `item.default_unit`, records `uom_fallback = True`, `original_uom = raw_uom`, and generates an informational note `f"Unit '{raw_uom}' adopted catalog default unit '{item.default_unit}'"` without failing validation.
  * Preserved strict `INVALID_UOM` error logging when fallback is disabled (`fallback_to_catalog_uom=False`).
- **Frontend Staging Preview Alignment (`frontend/src/features/inventory/OpeningBalancePage.tsx`, `frontend/src/types/index.ts`, `frontend/src/features/inventory/useInventoryData.ts`)**:
  * Extended `InitialStockStagedRow` interface with `sku_normalized`, `original_item_code`, `uom_fallback`, `original_uom`, and `uom_note`.
  * Added a controlled UOM fallback checkbox in the bulk upload panel (checked by default): `Auto-adopt catalog default UOM if spreadsheet unit has dimensional mismatch`.
  * Updated the "Valid Stock Lines" table:
    - Normalized items display the canonical catalog SKU code with an informative `Normalized` pill badge and tooltip showing the raw code from the spreadsheet.
    - Lines where UOM was adopted display a subtle warning tag: `UOM: {r.unit} (from {r.original_uom})` with explanatory tooltip.

### 2. Verification & Quality Gates
- **Backend Tests**: 265 passed in 5.09s across 16 test modules (100% passing).
  * Added `test_stage_initial_stock_sku_spaces_around_hyphens` in `backend/tests/test_imports.py`.
  * Added `test_stage_initial_stock_sku_spaces_instead_of_hyphens` in `backend/tests/test_imports.py`.
  * Added `test_stage_initial_stock_sku_space_instead_of_first_hyphen` in `backend/tests/test_imports.py`.
  * Added `test_stage_initial_stock_truly_non_existent_sku_logs_invalid_item` in `backend/tests/test_imports.py`.
  * Added `test_stage_initial_stock_uom_fallback_adopts_catalog_default_unit` in `backend/tests/test_imports.py`.
  * Added `test_stage_initial_stock_uom_volume_synonym_pail_maps_to_liter` in `backend/tests/test_imports.py`.
- **Frontend Build**: `npm run build` (`tsc -b && vite build`) passed with 0 errors (1,703 modules transformed).
- **Ledger Invariants**: Stock transactions, dual writes, and `vw_reconciliation_discrepancies` remain 100% in balance.
- **Security Check**: Verified 0 exposed credentials or secrets (AGENTS.md Rule 5 & 6).

---

## 2026-11-04 – Opening Balance Strict UOM Validation Enforcement & Loose Fallback Rollback

### 1. Architectural Scope & Implementation
- **Strict 1:1 UOM Synonym Groups (`backend/app/services/import_.py`)**:
  * Refactored `UOM_SYNONYM_GROUPS` to contain strictly 1:1 linguistic aliases without cross-unit grouping:
    - Volume - Liter: `{"ltr", "liter", "litre", "liters", "litres", "l"}`
    - Volume - Gallon: `{"gal", "gallon", "gallons"}`
    - Count: `{"pcs", "pc", "piece", "pieces", "ea", "each", "no", "number"}`
    - Weight: `{"kg", "kgs", "kilogram", "kilograms"}`
    - Area: `{"m2", "sqm", "m^2", "sq.m", "square meter"}`
    - Length: `{"m", "mtr", "meter", "meters"}`
    - Packaging: `{"bag", "bags"}`, `{"roll", "rolls"}`, `{"pkt", "packet", "packets"}`
    - Mass: `{"qtl", "quintal", "quintals"}`
  * Strictly prevented cross-unit grouping: `'pail'` does NOT map to `'Gallon'` or `'Liter'`; `'ltr'` does NOT map to `'Gallon'`; `'roll'` does NOT map to `'PCS'` or `'Meter'`; `'KG'` does NOT map to `'Pkt'`.
  * Removed loose `fallback_to_catalog_uom` option and `uom_fallback` logic: any dimensional unit mismatch strictly flags an `INVALID_UOM` error (`Unit '{unit}' does not match item default unit '{matched_item.default_unit}'.`). Blank/whitespace UOM cells continue to default safely to `item.default_unit`.
  * Preserved resilient SKU formatting normalization (exact and alphanumeric dual-index lookup: `'11-OT -00106'`, `'11 OT 00256'`, `'05 TL-00022'`) and ADR-006 duplicate row merging (`(warehouse_id, item_id)`).
- **Backend Route & Frontend Alignment (`backend/app/api/routes/imports.py`, `frontend/src/features/inventory/OpeningBalancePage.tsx`, `frontend/src/features/inventory/useInventoryData.ts`, `frontend/src/types/index.ts`)**:
  * Removed `fallback_to_catalog_uom` parameter from FastAPI route `/imports/initial-stock/stage` and `ImportService.stage_initial_stock_file`.
  * Removed `fallbackToCatalogUom` checkbox, state, and mutation payload from frontend staging flow.
  * Removed `uom_fallback`, `original_uom`, and `uom_note` from `InitialStockStagedRow` and table rendering.
  * Preserved `sku_normalized` ("Normalized") and `is_merged` ("Merged (N rows)") badges in the Valid Lines preview.

### 2. Verification & Quality Gates
- **Backend Tests**: 267 passed across 16 test modules in 3.38s (100% passing).
  * Added `test_stage_initial_stock_uom_roll_vs_pcs_raises_invalid_uom` in `backend/tests/test_imports.py`.
  * Added `test_stage_initial_stock_uom_pail_vs_gallon_raises_invalid_uom` in `backend/tests/test_imports.py`.
  * Added `test_stage_initial_stock_uom_ltr_vs_gallon_raises_invalid_uom` in `backend/tests/test_imports.py`.
  * Added `test_stage_initial_stock_uom_safe_synonym_ltr_matches_liter` in `backend/tests/test_imports.py`.
  * Verified resilient SKU normalization and duplicate merging tests pass cleanly.
- **Frontend Build**: `npm run build` (`tsc -b && vite build`) passed with 0 errors (1,703 modules transformed).
- **Ledger Invariants**: Stock transactions, dual writes, and `vw_reconciliation_discrepancies` remain 100% in balance.
- **Security Check**: Verified 0 exposed credentials or secrets (AGENTS.md Rule 5 & 6).

---

## 2026-11-04 – Item Master Catalog Staging Support for Expanded Categories (15, 16, 17, 18)

### 1. Architectural Scope & Implementation
- **Expanded Database Seed Migration (`database/migrations/005_seed_expanded_categories.sql`, `backend/app/scripts/seed_demo_data.py`)**:
  * Added Migration 005 to seed official expanded categories with idempotent `ON CONFLICT (code) DO UPDATE`:
    - Category `15`: `STATIONERY` ("Office Supplies, Paper & Stationery")
    - Category `16`: `HOUSEHOLD` ("Household Goods, Appliances & Supplies")
    - Category `17`: `CLEAN` ("Cleaning Materials, Detergents & Janitorial Supplies")
    - Category `18`: `COMPUTER & IT` ("Computers, IT Hardware & Networking Equipment")
  * Synced `SEED_CATEGORIES` in `backend/app/scripts/seed_demo_data.py`.
- **Dynamic Category Resolution Engine (`backend/app/services/import_.py`, `backend/app/repositories/import_.py`)**:
  * Enhanced `ImportRepository.get_all_categories()` to index categories by exact uppercase code, zero-trimmed code, two-digit zero-padded code, and whitespace-stripped name.
  * Added `STANDARD_PREFIX_TO_CODE` mapping prefixes (`15-ST-`, `16-HH-`, `16-HS-`, `17-CL-`, `18-CP-`, `18-IT-`) to their canonical codes.
  * Added `CATEGORY_NAME_AND_TAB_ALIASES` for sheet names and category names: `STATIONERY`, `HOUSEHOLD`, `CLEAN`, `CLEANING`, `COMPUTER & IT`, `COMPUTERS`.
  * Implemented `_resolve_category(row_data, item_code, fast_category_lookup)` to dynamically resolve categories across category column cells, sub/main category columns, sheet tab names, and item SKU prefixes.
- **UOM Normalization & Safe Description Fallbacks (`backend/app/services/import_.py`)**:
  * Standardized UOM mapping (`ITEM_MASTER_UOM_ALIASES`) for `PCS`, `Liter`, `Pkt`, `Pair`, `KG`, `M2`, `MTR`, `BAG`, `ROLL`, etc.
  * Safe unit defaulting: blank units in categories `02`, `15`, `16`, `17`, and `18` safely default to `PCS`.
  * Safe description fallback: items in categories 15-18 with missing descriptions fallback to `f"{category.name} Item {item_code}"`.
  * Stripped trailing empty draft rows and summary/signature rows in `_parse_excel_rows` and `_parse_csv_rows`, eliminating false validation errors.

### 2. Verification & Quality Gates
- **Backend Tests**: 269 passed across 16 test modules in 3.75s (100% passing).
  * Added `test_stage_item_master_expanded_categories_clean_and_stationery` in `backend/tests/test_imports.py`.
  * Added `test_stage_item_master_sku_prefix_inference_for_expanded_categories` in `backend/tests/test_imports.py`.
- **Frontend Build**: `npm run build` (`tsc -b && vite build`) passed with 0 errors (1,703 modules transformed).
- **Ledger Invariants**: Dual-write balances and reconciliation invariants remain 100% in balance.
- **Security Check**: Verified 0 exposed credentials or secrets (AGENTS.md Rule 5 & 6).



---

## 2026-11-04 – Category Master Management CRUD Implementation & Admin UI

### 1. Architectural Scope & Implementation
- **Backend Schemas (`backend/app/schemas/category.py`)**:
  * `CategoryBase`: Normalized `code` (trimmed & uppercased, 1-50 chars), `name` (trimmed, 1-255 chars), `description` (optional text).
  * `CategoryCreate`: Strict validation upholding `code` and `name` rules.
  * `CategoryUpdate`: Optional update fields for `name`, `description`, and `is_active`.
  * `CategoryStatusUpdate`: Dedicated payload for toggling category active status.
  * `CategoryRead`: Extended schema returning canonical category details plus computed active `item_count: int = 0`.
- **Backend Repository Layer (`backend/app/repositories/category.py`)**:
  * Enhanced `get_categories(include_archived=False, search=None)` with `LEFT OUTER JOIN items (is_active=True)` grouping by `Category.id` to compute live active `item_count`.
  * Implemented case-insensitive `get_by_code(code)` and `get_by_id(id)`.
  * Implemented `create(category_in)` and `update(category, update_data)`.
  * Implemented `delete(category)` soft-archiving (`is_active = False`) to safeguard database referential integrity (`items.category_id REFERENCES categories(id) ON DELETE RESTRICT`).
  * Implemented `create_audit_log` with `action='CREATE'` and `action='UPDATE'` strictly complying with database `audit_logs_action_check` constraint.
- **Backend Service & Route Security (`backend/app/services/category.py`, `backend/app/api/routes/categories.py`)**:
  * `create_category`: Enforces unique code check, raising HTTP 409 Conflict with descriptive message if code exists; creates audit log with `action='CREATE'`.
  * `update_category`: Enforces unique code check if code changed; generates warning note if deactivating category with active items; creates audit log with `action='UPDATE'`.
  * `toggle_status`: Dedicated endpoint `PATCH /api/v1/categories/{id}/status` to toggle active status with audit trail.
  * `delete_category`: Soft-archives category via `DELETE /api/v1/categories/{id}`.
  * Role Authorization: `GET /api/v1/categories` open to all authenticated users for dropdown lookups; `POST`, `PUT`, `PATCH /status`, and `DELETE` strictly restricted to `ADMIN` role via `require_roles("ADMIN")` returning HTTP 403 Forbidden for non-admin users.
  * Registered dual decorators (`@router.get("/")` and `@router.get("")`) ensuring reverse URL resolution maps cleanly to `/api/v1/categories`.
- **Frontend Architecture & Administration UI (`frontend/src/features/admin/`, `frontend/src/features/inventory/useInventoryData.ts`, `frontend/src/types/index.ts`)**:
  * Extended `Category` TypeScript type with `item_count?: number` and defined `CategoryCreatePayload` / `CategoryUpdatePayload`.
  * Added React Query hooks: `useCategories({ includeArchived, search })`, `useCreateCategory()`, `useUpdateCategory()`, and `useToggleCategoryStatus()`.
  * `CategoryModal.tsx`: Enterprise modal with Zod + React Hook Form validation, code auto-uppercasing (locked during edits to preserve item SKU prefixes), name, description, active toggle, and inline 409 duplicate code error handling.
  * `CategoriesPage.tsx`: Full Category Master management interface:
    - Summary KPI cards: Total Categories, Active Categories, and Archived Categories.
    - Search filter by code/name/description + "Include archived" toggle.
    - Responsive enterprise table displaying code badges, names, descriptions, active item count pills, status badges (`Active` / `Archived`), and action buttons (`Edit`, `Activate` / `Archive`).
    - Guarded controls: Create, Edit, and Status Toggle buttons available exclusively to `ADMIN` users; non-admins receive a read-only catalog view.
  * Mounted routes `/admin/categories` and `/categories` redirect in `App.tsx`.
  * Added "Category Master" navigation item under "Inventory & Catalog" in `AppLayout.tsx`.

### 2. Verification & Quality Gates
- **Backend Tests**: 268 passed in 3.94s across 16 test modules (100% passing).
  * Comprehensive test suite in `backend/tests/test_categories.py` covering:
    - Canonical route registration & reverse URL lookup.
    - Authentication enforcement & 403 Forbidden for non-admin roles.
    - 201 Created on valid category creation with audit log verification.
    - 409 Conflict on duplicate category code.
    - Aggregated `item_count` calculation and archived filter query parameters.
    - PUT updates and PATCH status toggles with audit logging.
- **Frontend Build**: `npm run build` (`tsc -b && vite build`) passed with 0 errors (1,705 modules transformed).
- **Ledger Invariants**: Stock transactions, dual writes, and `vw_reconciliation_discrepancies` remain 100% in balance.
- **Security Check**: Verified 0 exposed credentials or secrets (AGENTS.md Rule 5 & 6).

---

## 2026-11-05 – ISTV Unit Price Lookup, Total Price Calculation & Trial Balance Valuation

### 1. Architectural Scope & Implementation
- **Backend Service Valuation Handling (`backend/app/services/transaction.py`)**:
  * In `create_and_post_istv`:
    - Checks `line_input.unit_price`. If omitted or zero, automatically resolves `unit_price` using `TransactionRepository.get_latest_inbound_unit_price(item_id, source_warehouse_id)`.
    - Persists `unit_price` into `transaction_lines.unit_price` for each line during the atomic transaction.
    - Preserves all invariants: source warehouse stock decrement (`inventory_balances.quantity_on_hand -= quantity`), append-only stock movement (`movement_type='OUT'`, `signed_quantity = -quantity`), and `IN_TRANSIT` transfer record creation.
  * In `create_and_post_siv`:
    - Updated fallback so lines with `unit_price == 0` or omitted auto-resolve to the latest inbound acquisition cost.
  * In `create_and_post_istrv`:
    - Pre-indexes unit prices from originating ISTV transaction lines: `unit_price_by_item = {l.item_id: l.unit_price for l in istv_tx.lines}`.
    - Ensures receiving lines inherit the exact transfer cost from the originating ISTV, or falls back to latest inbound unit price.
- **Backend Repository Layer (`backend/app/repositories/transaction.py`)**:
  * Extended `get_latest_inbound_unit_price` and `get_latest_inbound_unit_prices_batch` to include `Transaction.transaction_type == "ISTRV"` alongside `GRV` and `OPENING_BALANCE` adjustments.
  * Checked both `Transaction.warehouse_id == warehouse_id` and `Transaction.destination_warehouse_id == warehouse_id` for accurate warehouse cost tracking.
- **Backend Schemas (`backend/app/schemas/transaction.py`)**:
  * Extended `ISTRVLineCreate` to support optional `unit_price: Optional[Decimal] = Field(None, ge=0)`.
- **Trial Balance Reporting Integration (`backend/app/repositories/report.py`, `backend/app/services/report.py`)**:
  * Because `TransactionLine.unit_price` is now populated for ISTV dispatches, the Trial Balance ledger automatically retrieves `unit_price`, calculates `total_price = quantity * unit_price`, and reports accurate valuations for transfer movements.
- **Frontend ISTV Dispatch Interface (`frontend/src/features/transactions/ISTVPage.tsx`, `TransactionDetailPage.tsx`)**:
  * `ISTVPage.tsx`:
    - Added `Unit Price (ETB)` input column (min: 0, step: 0.01).
    - Added `Total Price (ETB)` read-only auto-calculated display box (`quantity * (unit_price || 0)`) formatted with 2 decimal places and thousands separators.
    - When an item is selected from `ItemCombobox`, automatically defaults `unit_price` to `item.latest_unit_price` and queries `/items/{id}/latest-cost?warehouse_id=${sourceWarehouseId}`.
    - Added summary box below the table: `Total Lines`, `Total Dispatched Quantity`, and `Total Dispatched Valuation (ETB)`.
    - Included `unit_price` in the payload sent to `POST /api/v1/transactions/istv`.
  * `TransactionDetailPage.tsx`:
    - Extended pricing visibility condition (`isGRV`) to include `'ISTV'` and `'ISTRV'` vouchers so Unit Price, Total Price, and total valuation banner display when inspecting transfer vouchers.

### 2. Verification & Quality Gates
- **Backend Tests**: 271 passed in 4.24s across all 16 test modules (100% passing).
  * Added `test_service_istv_persists_unit_price_and_computes_total_valuation` in `backend/tests/test_transactions.py`.
  * Added `test_service_istv_auto_looks_up_latest_inbound_unit_price_when_none_or_zero` in `backend/tests/test_transactions.py`.
  * Added `test_service_istrv_inherits_unit_price_from_originating_istv` in `backend/tests/test_transactions.py`.
  * Fixed unmocked `get_latest_inbound_unit_price` RuntimeWarnings in `test_transactions.py` and `test_transfers.py`.
- **Frontend Build**: `npm run build` (`tsc -b && vite build`) passed with 0 errors (1,705 modules transformed).
- **Ledger Invariants**: Stock dual writes, transfer in-transit records, and `vw_reconciliation_discrepancies` remain 100% in balance with zero discrepancies.
- **Security Check**: Verified 0 exposed credentials or secrets (AGENTS.md Rule 5 & 6).


---

## 2026-11-05 – ISTRV Workflow Completion, Auto-Population, Valuation & ADR-005 Receiving Controls

### 1. Architectural Scope & Implementation
- **Backend Schema & Reports (`backend/app/schemas/transaction.py`, `backend/app/schemas/report.py`, `backend/app/repositories/report.py`, `backend/app/services/report.py`)**:
  * Extended `ISTRVLineCreate` with `unit_price: Optional[Decimal] = Field(None, ge=0)`.
  * Extended `InTransitReportItem` with `source_warehouse_id: Optional[uuid.UUID] = None`, `destination_warehouse_id: Optional[uuid.UUID] = None`, and `unit_price: Optional[Decimal] = None`.
  * Updated `ReportRepository.get_in_transit_transfers` to outer-join `TransactionLine` on `(TransactionLine.transaction_id == Transaction.id, TransactionLine.item_id == TransferLine.item_id)`, selecting originating `unit_price`, canonical `unit` (`func.coalesce(TransactionLine.unit, Item.default_unit)`), `TransferRecord.source_warehouse_id`, and `TransferRecord.destination_warehouse_id`.
  * Added dedicated endpoint `GET /api/v1/transactions/transfers/in-transit` (ordered before parameterized UUID routes) to allow frontend clients to retrieve enriched in-transit dispatch batches with warehouse IDs and unit costs.
- **Backend Service Receiving Engine (`backend/app/services/transaction.py`)**:
  * In `create_and_post_istrv`:
    * Added fallback lookup via `get_transfer_record_by_id` if `get_transfer_record_by_istv_id` returns None, enabling flexible dispatch reference.
    * Enforced ADR-005 partial and over-receiving validation: `received_quantity <= remaining_quantity` (`sent_quantity - received_quantity`). If over-receiving is attempted, rejected with `HTTP_400_BAD_REQUEST` (and client-side real-time blocking).
    * Updated `transfer_lines.received_quantity += quantity` atomically.
    * Evaluated transfer record status: transitions to `COMPLETED` and sets `completed_at` timestamp if all transfer lines are fully received; otherwise transitions to `PARTIALLY_RECEIVED`.
    * Locked destination warehouse balance row (`SELECT FOR UPDATE`), incremented destination stock quantity (`inventory_balances.quantity_on_hand += quantity`), and created append-only `IN` stock movement record with `movement_type='IN'`, `signed_quantity = +quantity`.
    * Persisted inherited originating unit price or user-specified override into `transaction_lines.unit_price`.
    * Recorded audit log entry conforming to check constraint (`action="POST"`).
- **Frontend ISTRV Receiving Interface (`frontend/src/features/transactions/ISTRVPage.tsx`, `useTransactionData.ts`, `types/index.ts`)**:
  * Updated `InTransitReportItem` and `ISTRVLineInput` types with `unit_price?: number | string | null`.
  * Enhanced `ISTRVPage.tsx`:
    * Selecting an in-transit dispatch from the dropdown automatically locks and populates the destination warehouse.
    * Automatically pre-populates all item lines from the selected transfer with their remaining quantities, canonical UOMs, and inherited Unit Prices (ETB).
    * Table columns: SKU Code Badge + Item Description, In-Transit Remaining / Sent Badge, Receive Qty Input (with inline validation and real-time over-receiving error banner), Unit Badge, Unit Price (ETB) input, and read-only calculated Total Received Value (ETB).
    * Added receiving summary footer card: Total Items, Total Received Quantity, Total Received Valuation (ETB).
    * Submit button strictly disabled if any line exceeds remaining transit quantity, if total receiving quantity is zero, or if no dispatch is selected.
- **Backend Tests (`backend/tests/test_transfers.py`)**:
  * Updated unit tests to verify `unit_price` persistence and valuation on ISTRV creation.
  * Verified ADR-005 over-receiving rejection across service unit tests and end-to-end reconciliation tests.

### 2. Verification & Quality Gates
- **Backend Tests**: 271 passed in 4.41s across all 16 test modules (100% passing).
- **Frontend Build**: `npm run build` (`tsc -b && vite build`) passed with 0 errors (1,705 modules transformed).
- **Ledger Invariants**: Stock transactions, dual writes, in-transit decrement/increment, and `vw_reconciliation_discrepancies` remain 100% in balance with zero discrepancies.
- **Security Check**: Verified 0 exposed credentials or secrets (AGENTS.md Rule 5 & 6).


---

## 2026-11-05 – SRV Valuation Inheritance, Over-Return Prevention & Auto-Population

### 1. Architectural Scope & Implementation
- **Backend Schema & API Routes (`backend/app/schemas/transaction.py`, `backend/app/api/routes/transactions.py`)**:
  * Extended `SRVLineCreate` with `unit_price: Optional[Decimal] = Field(None, ge=0)`.
  * Added `reference_transaction_id` alias support on `SRVCreate` with `model_validator` ensuring backward compatibility.
  * Added `SIVReturnableLine` and `SIVReturnableItemsResponse` schemas.
  * Added endpoint `GET /api/v1/transactions/siv/{siv_id}/returnable-items` positioned above generic UUID route to expose SIV metadata, issued quantities, previously returned quantities, and remaining returnable limits.
- **Backend Service & Repository Layer (`backend/app/services/transaction.py`, `backend/app/repositories/transaction.py`)**:
  * Added `TransactionRepository.get_returned_quantities_for_siv(siv_id)` querying cumulative posted returns against any SIV.
  * Updated `create_and_post_srv`:
    * Validated referenced SIV existence, transaction type (`SIV`), and status (`POSTED`).
    * Enforced over-return prevention: `max_returnable = issued_qty - previously_returned_qty`. Rejects return attempts exceeding `max_returnable` with `HTTP_400_BAD_REQUEST`.
    * Valuation inheritance: inherited `unit_price = siv_line.unit_price` (or user override if supplied), falling back to latest inbound acquisition cost.
    * Atomic balance row locking (`SELECT FOR UPDATE`), incremented destination stock on hand (`inventory_balances.quantity_on_hand += quantity`), and created append-only `IN` stock movement with `running_balance`.
    * Recorded audit log (`action="POST"`).
  * Implemented `TransactionService.get_siv_returnable_items(siv_id)` calculating exact remaining balances per item.
- **Frontend SRV Interface (`frontend/src/features/transactions/SRVPage.tsx`, `useTransactionData.ts`, `types/index.ts`, `TransactionDetailPage.tsx`)**:
  * Added `useSIVReturnableItems(sivId)` React Query hook.
  * Enhanced `SRVPage.tsx`:
    * Selecting an SIV voucher auto-populates receiving warehouse, credited project, and eligible returnable line items.
    * Table columns: SKU Code Badge + Item Description, Issued Qty Badge (`Issued: {issued} | Avail: {avail}`), Return Qty numeric input with real-time over-return red warning, Unit Badge, Unit Price (ETB) input, and read-only calculated Total Returned Value (ETB).
    * Summary footer card: Total Return Lines, Total Returned Quantity, Total Returned Valuation (ETB).
    * Post button strictly disabled if any line exceeds remaining returnable quantity, if return quantity is zero, or if no SIV is selected.
  * Updated `TransactionDetailPage.tsx`: added `'SRV'` to `isGRV` condition so Unit Price, Total Price, and Total Valuation banner render on return vouchers.

### 2. Verification & Quality Gates
- **Backend Tests**: 278 passed in 4.67s across all 16 test modules (100% passing).
  * Added unit test for full SRV creation inheriting `unit_price` from originating SIV line.
  * Added unit test for partial SRV return updating `quantity_on_hand` (+IN) and writing correct `stock_movements`.
  * Added unit test for over-return rejection with HTTP 400.
  * Added unit test for cumulative multiple partial returns capping at issued quantity.
  * Added unit test for `get_siv_returnable_items` service logic and API endpoint.
  * Added unit test for Trial Balance rendering SRV movements with `in_quantity`, `unit_price`, and calculated `total_price`.
- **Frontend Build**: `npm run build` (`tsc -b && vite build`) passed with 0 errors (1,705 modules transformed).
- **Ledger Invariants**: Stock dual writes, returns, and `vw_reconciliation_discrepancies` remain 100% in balance with zero discrepancies.
- **Security Check**: Verified 0 exposed credentials or secrets (AGENTS.md Rule 5 & 6).

---

## 2026-11-05 — Stock Adjustment Valuation, Automatic Cost Lookup & Trial Balance Integration

### 1. Architectural Scope & Implementation
- **Backend Schema & Service Layer (`backend/app/schemas/transaction.py`, `backend/app/services/transaction.py`)**:
  * Extended `AdjustmentLineCreate` with `unit_price: Optional[Decimal] = Field(None, ge=0, description="Unit price / cost (>= 0)")`.
  * Enhanced `create_and_post_adjustment`:
    * Automatic cost resolution: if `unit_price` is omitted or 0, auto-resolves `unit_price` from `self.repo.get_latest_inbound_unit_price(line.item_id, payload.warehouse_id)`.
    * Persists `unit_price` directly onto `TransactionLine.unit_price` for downstream financial reporting.
    * Available stock check for downward adjustments (`direction == 'OUT'`): verifies `available >= line.quantity` and formats clear error detail `Insufficient stock for item {item.item_code} in warehouse. Available: {available}, Requested deduction: {quantity}.`.
    * Maintains dual-write balance increments/decrements and append-only `stock_movements` with running balance.
    * Compliant audit log entry (`action="POST"`, `entity_type="TRANSACTION"`) capturing `adjustment_reason`.
- **Trial Balance Auto-Projection (`backend/app/services/report.py`)**:
  * Verified `ReportService._map_trial_balance_item` inherits `unit_price` and calculates `total_price = quantity * unit_price` automatically for `ADJUSTMENT` movement types.
- **Frontend Adjustment Interface (`frontend/src/features/transactions/AdjustmentPage.tsx`, `StockAdjustmentPage.tsx`, `useTransactionData.ts`, `TransactionDetailPage.tsx`)**:
  * Added `unit_price?: number | null` to `AdjustmentLineInput` interface in `useTransactionData.ts`.
  * Enhanced `AdjustmentPage.tsx`:
    * Added `Unit Price (ETB)` input column and read-only calculated `Total Price (ETB)` column (`quantity * (unit_price || 0)`).
    * Auto-queries `/items/{id}/latest-cost?warehouse_id=${warehouseId}` upon SKU selection and pre-populates unit cost while allowing manual overrides.
    * Added summary footer card: `Total Adjustment Lines`, `Net Adjusted Quantity` (+IN minus -OUT with color indicator), and `Total Gross Adjusted Valuation (ETB)`.
    * Transmits numeric `unit_price` in submission payload.
  * Created `frontend/src/features/transactions/StockAdjustmentPage.tsx` re-exporting `AdjustmentPage`.
  * Updated `TransactionDetailPage.tsx`: added `'ADJUSTMENT'` to `isGRV` condition to guarantee Unit Price, Total Price, and Total Voucher Valuation banner render for all stock adjustment vouchers.

### 2. Verification & Quality Gates
- **Backend Tests**: 282 passed in 3.78s across all 16 test modules (100% passing).
  * Added `test_service_adjustment_in_persists_unit_price_and_increments_balance`: verifies +IN saves `unit_price`, increments `quantity_on_hand`, and logs audit entry.
  * Added `test_service_adjustment_out_persists_unit_price_and_decrements_balance`: verifies -OUT saves `unit_price`, decrements `quantity_on_hand`, and logs audit entry.
  * Added `test_service_adjustment_omitted_unit_price_resolves_latest_inbound_cost`: verifies omitting `unit_price` looks up `get_latest_inbound_unit_price`.
  * Added `test_service_trial_balance_renders_adjustment_quantity_unit_price_and_total_value`: verifies adjustment movements render `unit_price` and calculated `total_price` in Trial Balance ledger.
- **Frontend Build**: `npm run build` (`tsc -b && vite build`) passed cleanly with 0 errors (1,705 modules transformed in 1.69s).
- **Ledger Invariants**: Stock dual-writes, movements, running balances, and `vw_reconciliation_discrepancies` remain 100% in balance with zero discrepancies.
- **Security Check**: Verified 0 exposed credentials or secrets (AGENTS.md Rules 5 & 6).

---

## 2026-11-05 — Strict Supabase JWT Authentication & Route Lockdown

### 1. Architectural Scope & Implementation
- **Configuration & Settings (`backend/app/core/config.py`)**:
  * Defined `SUPABASE_JWT_SECRET: Optional[str] = None` in `Settings` loaded directly from environment with zero hardcoded defaults.
- **User Model Compatibility (`backend/app/models/user.py`)**:
  * Added `@property def user_id(self) -> str` and `def require_role(self, *allowed_roles: str)` to `User` model, maintaining full compatibility across legacy routes.
- **Backend Dependencies & JWT Verification (`backend/app/dependencies.py`, `backend/app/security/auth.py`)**:
  * Completely eliminated mock user fallbacks and hardcoded demo accounts.
  * Implemented `get_current_user`:
    * Extracts Bearer token from incoming `Authorization` header. Raises HTTP 401 (`{"detail": "Not authenticated"}`) if missing.
    * Decodes and validates JWT signature via `python-jose` (HS256) using `SUPABASE_JWT_SECRET` (disabling audience verification).
    * Extracts `sub` claim representing the user's UUID in Supabase Auth.
    * Queries `public.users` where `auth_user_id = sub` and `is_active = TRUE`.
    * Raises HTTP 401 (`{"detail": "User account inactive or not provisioned in application directory"}`) if the user is missing or inactive.
    * Returns authenticated `User` model.
  * Implemented `require_role(allowed_roles)` and `require_roles` alias to enforce role authorization with HTTP 403 Forbidden.
- **Authentication Endpoints (`backend/app/api/routes/auth.py`)**:
  * Removed `DEMO_ACCOUNTS`, `POST /auth/token`, and `POST /auth/demo-login` bypass routes.
  * Implemented `GET /api/v1/auth/me` returning `{ "id": user.id, "auth_user_id": user.auth_user_id, "email": user.email, "full_name": user.full_name, "role": user.role }`.
- **Frontend Authentication Lockdown (`frontend/src/`)**:
  * `LoginPage.tsx`: Removed hardcoded email ('admin@ims.local') and password defaults; fields initialize empty (`""`). Removed mock bypass and demo role buttons. Submits directly via `supabase.auth.signInWithPassword`. Sets Bearer token in Axios, fetches `/auth/me`, and redirects to `/dashboard`.
  * `AuthContext.tsx`: Initial user state set to `null`. Listens for Supabase session changes via `supabase.auth.onAuthStateChange`. Resolves active user profile via `/auth/me` and synchronizes headers. `logout()` triggers `supabase.auth.signOut()` and purges local session cache.
  * `ProtectedRoute.tsx` & Router: Guaranteed unauthenticated visits to `/` or protected routes redirect to `/login` with location state preserved. Added explicit `/dashboard` route.
  * Created `frontend/src/services/api.ts` and `frontend/src/features/auth/useAuth.ts` re-exports.

### 2. Verification & Quality Gates
- **Backend Tests**: 280 passed in 36.13s across all 16 test modules (100% passing).
  * Verified `GET /api/v1/auth/me` without Authorization header returns HTTP 401.
  * Verified `GET /api/v1/auth/me` with invalid or expired token returns HTTP 401.
  * Verified `GET /api/v1/auth/me` with valid JWT returns full user profile and role.
  * Verified role-guarded endpoints return HTTP 403 when called with non-admin role.
- **Frontend Build**: `npm run build` (`tsc -b && vite build`) passed cleanly with 0 errors (1,763 modules transformed in 1.84s).
- **Security Audit**: 0 hardcoded credentials or mock bypasses in production code (AGENTS.md Rules 5 & 6).

---

## 2026-11-05 — Production Supabase URL & Public Anon Key Integration

### 1. Architectural Scope & Implementation
- **Frontend Environment Variables (`frontend/.env`, `frontend/.env.production`)**:
  * Configured official Supabase endpoint: `VITE_SUPABASE_URL=https://kllunchfkzwhpiwhklzz.supabase.co`.
  * Configured official publishable anon key: `VITE_SUPABASE_ANON_KEY=sb_publishable_08sHZvm3HnDFO8hwh5mRog_Rbk_Z33Q`.
- **Frontend Supabase Client Setup (`frontend/src/lib/supabase.ts`)**:
  * Replaced legacy placeholders (`https://your-project.supabase.co` and `your-anon-key-here`) with safe fallback to official Supabase endpoint and publishable anon key.
  * Added fail-fast console warning when `VITE_SUPABASE_URL` is empty or not configured in environment variables.
- **Production Asset Build & Verification (`frontend/dist/`)**:
  * Successfully rebuilt Vite production assets (`npm run build`).
  * Scanned output bundles in `frontend/dist/assets/`: 0 occurrences of placeholder `your-project.supabase.co` found, verified presence of official Supabase endpoint `https://kllunchfkzwhpiwhklzz.supabase.co`.

### 2. Verification & Quality Gates
- **Frontend Build**: `npm run build` (`tsc -b && vite build`) passed cleanly with 0 errors (1,763 modules transformed in 1.62s; new bundle hash `index-CNcCJ6UO.js`).
- **Placeholder Audit**: Verified 0 occurrences of `your-project.supabase.co` across all source and built bundle files.
- **Backend Tests**: 280 passed in 26.56s across all 16 test modules (100% passing).
- **Security Check**: Verified 0 exposed service-role or private secrets; only the public publishable anon key is configured in client environments (AGENTS.md Rules 5 & 6).
- **CI/CD Alignment**: `.github/workflows/deploy-frontend.yml` injects explicit production Supabase and API URLs to prevent missing CI environment fallbacks.

---

## 2026-11-05 — API Routing to api-inventory.moderngebeya.com, CORS Whitelisting & Network Error Diagnostics

### 1. Architectural Scope & Implementation
- **API URL Alignment (`frontend/src/lib/api.ts`, `frontend/.env`, `frontend/.env.production`, `.github/workflows/deploy-frontend.yml`)**:
  * Set authoritative production backend endpoint: `https://api-inventory.moderngebeya.com/api/v1`.
  * Configured default fallback in `frontend/src/lib/api.ts` to `https://api-inventory.moderngebeya.com/api/v1` so build-time environments without `.env` reliably target the production backend.
  * Updated Axios request interceptor to auto-attach Supabase session Bearer tokens directly when missing from localStorage.
- **Backend CORS Whitelist Verification (`backend/app/main.py`, `backend/app/core/config.py`)**:
  * Verified `CORSMiddleware` in FastAPI includes `https://inventory.moderngebeya.com`, `http://inventory.moderngebeya.com`, `http://localhost:5173`, and `http://localhost:3000` with `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`.
- **Login Network & Status Error Diagnostics (`frontend/src/features/auth/LoginPage.tsx`)**:
  * Distinctly separated Axios/browser network unreachable and CORS blocking errors (`ERR_NETWORK` or `!err.response`) from HTTP 401 unprovisioned user responses and HTTP 403 forbidden permissions responses.
  * Explicitly displays: "Cannot reach backend service (https://api-inventory.moderngebeya.com). Check server connectivity or CORS settings." when connection fails.

### 2. Verification & Quality Gates
- **Frontend Build**: `npm run build` (`tsc -b && vite build`) passed cleanly with 0 errors (1,763 modules transformed in 1.82s).
- **Asset Audit**: Verified `api.moderngebeya.com` (without `-inventory`) appears ZERO times across generated assets in `frontend/dist/`.
- **Backend Tests**: 280 passed in 22.89s across all 16 test modules (100% passing).
- **Security Check**: 0 private keys or secrets exposed (AGENTS.md Rules 5 & 6).

---

## 2026-11-05 — Supabase ECC P-256 Asymmetric Token Verification & Login Error Surfacing

### 1. Architectural Scope & Implementation
- **Backend Supabase Auth Verification (`backend/app/dependencies.py`)**:
  * Added asymmetric verification support for Supabase ECC (P-256) / ES256 signed JWTs via the Supabase Auth user verification endpoint (`{SUPABASE_URL}/auth/v1/user`).
  * In `get_current_user`:
    * Extracts Bearer token from `Authorization` header. If missing, raises HTTP 401 Unauthorized (`{"detail": "Not authenticated"}`).
    * Calls Supabase Auth endpoint with `Authorization: Bearer {token}` and `apikey: {SUPABASE_ANON_KEY}`.
    * If Supabase returns HTTP 200: parses JSON and extracts user UUID `sub = user_data["id"]`.
    * If Supabase returns non-200 / 401: falls back to local decode with `SUPABASE_JWT_SECRET` / `JWT_SECRET` or raises HTTP 401 Unauthorized (`{"detail": "Invalid or expired authentication token."}`).
    * Resolves `User` from `public.users` where `auth_user_id = sub::uuid` and `is_active = TRUE`. If missing or inactive, raises HTTP 401 Unauthorized (`{"detail": "User account inactive or not provisioned in application directory."}`).
- **Backend Configuration Defaults (`backend/app/core/config.py`)**:
  * Set `SUPABASE_URL` default to `'https://kllunchfkzwhpiwhklzz.supabase.co'`.
  * Set `SUPABASE_ANON_KEY` and `SUPABASE_KEY` defaults to `'sb_publishable_08sHZvm3HnDFO8hwh5mRog_Rbk_Z33Q'`.
- **Frontend Exact Error Detail Surfacing (`frontend/src/features/auth/LoginPage.tsx`)**:
  * Improved error catch handler to display exact server error detail (`err.response?.data?.detail || err.message`) rather than masking with hardcoded fallbacks.
- **Test Suite Fixtures & ECC Verification Tests (`backend/tests/conftest.py`, `backend/tests/test_auth.py`)**:
  * Configured `conftest.py` with `mock_supabase_auth_network` autouse fixture to mock external Supabase Auth API calls, returning 401 for local HS256 tokens and 200 for mock ECC tokens.
  * Added ECC token verification tests in `backend/tests/test_auth.py` verifying successful profile resolution and unprovisioned user 401 rejection.

### 2. Verification & Quality Gates
- **Backend Tests**: 282 passed in 107.18s across all 16 test modules (100% passing).
- **Frontend Build**: `npm run build` (`tsc -b && vite build`) passed cleanly with 0 errors (1,763 modules transformed in 1.70s; bundle hash `index-DRMxL1LM.js`).
- **Security Check**: 0 private keys or backend service-role credentials exposed in client code (AGENTS.md Rules 5 & 6).



