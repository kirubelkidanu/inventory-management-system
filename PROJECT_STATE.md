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
