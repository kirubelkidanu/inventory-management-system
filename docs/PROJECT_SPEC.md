# Inventory Management System — Project Specification

## 1. Purpose

Build a secure, web-based inventory management system to replace the company's current Excel-based inventory workflow.

The first 15-day release is an MVP for a construction-material inventory operation. The system must track what items exist, their quantities, the warehouse/project where stock is held, every movement in and out, transfers, items in transit, references between related transactions, and a detailed Trial Balance / transaction report.

The uploaded Excel workbook is real source data supplied by the client. It is the initial item master dataset, not demo data.

## 2. Current client data

The authoritative workbook contains 15 sheets (14 active data sheets and 1 blank sheet named `Sheet4`), totaling 5,646 unique inventory items.

The common item fields across sheets are:
- Major Category (`main catagories`, `major category`, `Major category`)
- Inventory ID (`inventory id`, `Inventory id`)
- Description (`description`, `Description`, `Descrption`)
- Subcategory Code (`sub gatagory code`, `sub category`, `Sub category`)
- Unit Measurement (`unit measurment`, `Unit measurment`)

The categories and ID prefixes from the authoritative workbook are:
1. `CEMENT` (40 items) — Prefix: `01-CM-` (e.g. `01-CM-00001` .. `01-CM-00040`)
2. `STEEL` (569 items) — Prefix: `02-ST-` (e.g. `02-ST-00001` .. `02-ST-00569`) *(Note: UOM column is blank for all 569 items)*
3. `QURRY` (16 items) — Prefix: `03-QR-` (e.g. `03-QR-00001` .. `03-QR-00016`)
4. `LAND SCAPE` (3 items) — Prefix: `04-GL-` (e.g. `04-GL-00001` .. `04-GL-00003`)
5. `Tiles` (178 items) — Prefix: `05-TL-` (e.g. `05-TL-00001` .. `05-TL-00178`)
6. `WOOD,P,GGG` (78 items) — Prefix: `06-WD-` (e.g. `06-WD-00001` .. `06-WD-00078`)
7. `PAINT AND CHEMICAL` (159 items) — Prefix: `07-PC-` (e.g. `07-PC-00001` .. `07-PC-00158`, plus corrupt draft row `07-PC-D0159`)
8. `SANIT` (1,401 items) — Prefix: `08-SN-` (e.g. `08-SN-00001` .. `08-SN-01401`)
9. `ELECTRIC` (141 items) — Prefix: `09-EL-` (e.g. `09-EL-00001` .. `09-EL-00141`)
10. `safety&security` (117 items) — Prefix: `10-SF-` (e.g. `10-SF-00001` .. `10-SF-00117`)
11. `OTHER` (294 items) — Prefix: `11-OT-` (e.g. `11-OT-00001` .. `11-OT-00294`)
12. `FL` (35 items) — Prefix: `12-FL-` (e.g. `12-FL-00001` .. `12-FL-00035`)
13. `TB` (139 items) — Prefix: `13-TB-` (e.g. `13-TB-00001` .. `13-TB-00139`)
14. `SPARE PART` (2,476 items) — 8 equipment/vehicle sub-prefixes:
    - `14-TY-` (670 items, Toyota Vitz/Corolla/D4D/Dolphin — subcategories populated `14-01`..`14-05`)
    - `14-SN-` (606 items, Sinotruk)
    - `14-IZ-` (384 items, ISUZU)
    - `14-XL-` (353 items, XCMG)
    - `14-BL-` (223 items, JCB)
    - `14-ER-` (151 items, Euro Trakker)
    - `14-HT-` (62 items, Hitachi)
    - `14-CG-` (27 items, Caterpillar)
15. `Sheet4` (0 items, Blank sheet)

Total item master dataset: **5,646 items**.

The current sample/initial warehouse is:
- Code: WH001
- Project: Kazanchis

Warehouse code must NOT permanently encode the project name. A warehouse is a separate entity related to a project/location. Future examples may include WH002 for Entoto or another project.

## 3. Core business requirement

The system must maintain an auditable inventory ledger.

Every stock-changing event must be represented by a transaction and transaction lines. Current stock must be derived from valid stock movements, not from arbitrary direct quantity edits.

Core transaction types:

| Code | Meaning | Normal stock effect |
|---|---|---|
| GRV | Goods Receiving Voucher / Receipt | IN |
| SIV | Store Issue Voucher / Issue | OUT |
| ISTV | Inter-Store Transfer Voucher | OUT from source + IN TRANSIT |
| ISTRV | Inter-Store Transfer Receiving Voucher | IN to destination + completes transit |
| SRV | Store Return Voucher / Return against SIV | IN |
| ADJUSTMENT | Stock correction | IN or OUT |

Transaction Entry is the main workflow/screen for entering transactions. The UI may provide separate shortcuts for each transaction type.

## 4. In-transit requirement

Transfers are not assumed to be instantly received.

Example:
1. WH001 sends 100 units to WH002 through ISTV.
2. Source stock decreases by 100.
3. 100 becomes IN TRANSIT.
4. WH002 does not receive the stock yet.
5. When ISTRV references the ISTV, destination stock increases by the received quantity and the transit quantity is reduced/completed.

The system must prevent a transfer from disappearing or being counted at both warehouses before receipt.

## 5. References

References are mandatory where business flow requires them.

Examples:
- ISTRV must reference the originating ISTV.
- SRV should reference the original SIV.
- Related/correcting transactions must retain references to their source transaction.
- The Trial Balance/report must display reference information.

References must be searchable.

## 6. Stock rules

### GRV (Goods Receiving Voucher)
- Adds stock to a warehouse.
- Confirmed physical document fields:
  - Header: Store No. / Store Location, Supplier, Received GRV No., Invoice No., Date.
  - Lines: Description, Qty, Unit, Remark.
  - *Observed physical fields requiring client policy confirmation*: Unit Price, Total Price.
- Requires warehouse, project/store, date, item lines, quantities, and transaction/GRV number.
- Cannot accept zero or negative quantity.

### SIV (Store Issue Voucher)
- Removes stock from a warehouse.
- Confirmed physical document fields:
  - Header: Store Location, Requested From, Project/Dept, Requested No., Material (header description), Date, SIV No.
  - Lines: Item Code, Description, UOM, Qty, Remark.
  - Signatures: Issued By, Checked By, Received By, Approved By.
- Cannot issue more available stock than permitted by business rules.
- Must record who entered it, who approved/checked/received it, and when.

### ISTV (Inter-Store Transfer Voucher)
- Moves stock out of a source warehouse.
- Creates an in-transit quantity.
- Confirmed physical document fields:
  - Header / Logistics: FROM (Source Store), TO (Destination Store), MATERIAL, Plate No. (Vehicle Plate), Driver Name, Date, ISTV No.
  - Lines: Item Code, Description, UOM, Qty, Remark.
  - Signatures: Authorization / Dispatch / Driver Handover.
- Requires source warehouse and destination warehouse (must be different).
- Quantity cannot exceed transferable stock.
- Must have a unique transfer/transaction number and driver/plate tracking.

### ISTRV (Inter-Store Transfer Receiving Voucher)
- Receives stock into destination warehouse.
- Must reference a valid originating ISTV.
- Received quantity cannot exceed remaining quantity in transit.
- Supports partial receipt only if the client confirms that partial receipt is allowed.
- Completing the remaining quantity closes the transfer.

### SRV (Store Return Voucher)
- Returns material into a warehouse.
- Should reference an original SIV.
- Return quantity must follow the client's allowed-return rules.
- Stock increases by the accepted return quantity.

### ADJUSTMENT
- Corrects physical/system discrepancies.
- Requires reason.
- Requires authorization.
- Must be fully audited.
- Must never silently overwrite historical movements.

## 7. Inventory master

Phase 1:
- Import existing items from Excel.
- Search and view items.
- Keep existing inventory IDs.
- Preserve descriptions, categories, subcategory codes and units.

Phase 2:
- Item Maintenance.
- Create/maintain new inventory codes.
- The exact code-generation rule must be confirmed with the client before automatic generation is implemented.
- Do not invent a code-generation formula.

## 8. Warehouses and projects

Warehouse:
- Unique warehouse code, e.g. WH001.
- Name/label.
- Project association.
- Location.
- Active/inactive status.

Project:
- Unique project identifier.
- Project name, e.g. Kazanchis.
- Location/details as required.
- Active/inactive status.

Do not hardcode Kazanchis into business logic.

## 9. Required screens

MVP:
1. Login
2. Dashboard
3. Inventory / Items
4. Warehouses
5. Projects
6. Transaction Entry
7. GRV
8. SIV
9. ISTV
10. ISTRV
11. SRV
12. Adjustment
13. In Transit
14. Reports
15. Trial Balance
16. Lookup / Search
17. Transaction Details

Phase 2:
18. Item Maintenance
19. Advanced administration/configuration

## 10. Trial Balance / primary report

This is the highest-priority report.

It must show detailed inventory movement, not just final quantities.

Minimum columns:
- Date
- Transaction number
- Transaction type
- Reference
- Item ID
- Description
- Category
- Subcategory
- Unit
- Warehouse
- Project
- IN quantity
- OUT quantity
- Running balance where applicable
- Status
- Entered by
- Created date/time

Required filters:
- Date from/to
- Warehouse
- Project
- Item
- Category
- Transaction type
- Reference
- Status

Required actions:
- View transaction details
- Search
- Filter
- Sort
- Export to Excel
- Print/PDF can follow after the core report is correct

The report must be reproducible from transaction data.

## 11. Lookup

Lookup must allow users to trace:
- Item by inventory ID
- Description
- Warehouse
- Project
- Transaction number
- Reference
- Transaction type
- Date range

An item history view should show all movements affecting that item.

## 12. Editing and audit

Historical stock-changing transactions must not be silently overwritten.

Preferred workflow:
- Posted transaction remains immutable or controlled.
- Authorized user can request/carry out a correction.
- Original values are retained in audit history.
- Correction records who changed it, when, what changed, and why.

Do not implement unrestricted DELETE for posted transactions.

## 13. Users and roles

Initial roles:
- Admin
- Inventory Manager
- Store Keeper
- Viewer

Permissions must be enforced server-side, not only by hiding frontend buttons.

Example:
- Viewer: view inventory/reports/lookup.
- Store Keeper: enter operational transactions.
- Inventory Manager: operational transactions, adjustments, controlled edits/reviews, reports.
- Admin: users, roles, warehouse/project setup, system administration.

Exact approval workflow can be expanded after client confirmation.

## 14. Security requirements

- Never expose Supabase service-role/secret keys to the frontend.
- Store secrets in environment variables.
- Validate every request on the backend.
- Enforce authorization server-side.
- Use PostgreSQL constraints for important invariants.
- Use transactions/atomic database operations for stock-changing operations.
- Enable and correctly configure Row Level Security where applicable.
- Log important security and data changes.
- Do not commit secrets to Git.
- Do not allow arbitrary client-side stock updates.
- Do not trust quantities, roles, warehouse IDs or item IDs supplied by the browser without validation.

## 15. Technology stack

Frontend:
- React
- TypeScript
- Vite
- Tailwind CSS
- shadcn/ui
- TanStack Query
- React Hook Form
- Zod

Backend:
- Python
- FastAPI
- Pydantic
- SQLAlchemy or a carefully chosen PostgreSQL data-access layer
- Alembic for migrations

Database/infrastructure:
- Supabase
- PostgreSQL
- Supabase Auth
- PostgreSQL RLS where applicable

Tools:
- Git
- GitHub
- Google Antigravity as primary coding agent
- pytest
- Playwright
- openpyxl
- ReportLab later for PDF

## 16. Non-goals for the 15-day MVP

Do NOT build unless the client explicitly adds them:
- Mobile app
- AI chatbot
- Barcode/QR scanning
- Procurement module
- Full accounting/GL integration
- Payroll
- Supplier CRM
- Advanced forecasting
- Multi-company SaaS
- Microservices
- Kubernetes
- Complex notification infrastructure

## 17. Definition of success

The MVP is successful when a client user can:
1. Log in.
2. See real inventory items imported from the supplied Excel.
3. See WH001 / Kazanchis.
4. Receive stock with GRV.
5. Issue stock with SIV.
6. Transfer stock with ISTV.
7. See the transferred quantity in transit.
8. Receive the transfer with ISTRV.
9. Return stock with SRV referencing SIV.
10. Make an authorized adjustment with a reason.
11. See current balances.
12. Search/lookup items and transactions.
13. View the complete transaction history.
14. Generate the detailed Trial Balance.
15. Verify the calculated balances against manually calculated scenarios.

## 18. Unconfirmed items & Client Clarification Checklist

Do not invent these rules. Ask the client before implementing them:

### High Priority Master Data & Transaction Clarifications:
1. **Steel Units of Measure (569 items)**: All 569 items in sheet `STEEL` have blank `unit measurment` column in the workbook. Confirm the correct UOMs (e.g. `Pcs`, `Kg`, `Meter`, `Qtl`, etc.) before import.
2. **GRV Unit Price and Total Price**: Physical GRV vouchers contain `Unit Price` and `Total Price`. Confirm whether financial tracking/pricing and stock valuation should be part of the MVP database or if it remains purely a quantity ledger. *(Do NOT add pricing columns to the database without explicit client confirmation)*.
3. **Spare Part Subcategories (1,806 items)**: Only Toyota spare parts (`14-TY-`) have populated subcategories (`14-01`..`14-05`). The other 7 equipment types (`14-SN-`, `14-IZ-`, `14-XL-`, `14-BL-`, `14-ER-`, `14-HT-`, `14-CG-`) have blank subcategory fields. Confirm if subcategories should be generated, left optional, or provided in an updated sheet.
4. **Paint & Chemical Trailing Row Anomaly**: Row 161 of `PAINT AND CHEMICAL` contains an ID `07-PC-D0159` with blank description, major category, subcategory, and UOM. Confirm this row is an invalid draft to exclude during import.
5. **SIV Four-Signatory Approval Workflow**: Physical SIV has 4 signature blocks (`Issued By`, `Checked By`, `Received By`, `Approved By`). Confirm if the system should enforce a multi-step digital approval state machine or simply record the names/signatories from physical vouchers.
6. **Physical Document Voucher Numbering vs. System Sequence**: Physical documents have pre-printed / written numbers (`SIV No.`, `ISTV No.`, `Received GRV No.`, `Invoice No.`). Confirm the numbering rules and whether physical voucher numbers are stored as primary transaction numbers or external reference fields.
7. **Transfer Rules**: Whether partial ISTRV receipt is allowed, and whether one ISTV can be received across multiple separate ISTRV batches.
8. **Negative Stock Policy**: Whether stock is strictly prevented from going below zero across all transactions.
9. **Return & Adjustment Policies**: Exact SRV allowed-return window/rules and Adjustment authorization hierarchy.
10. **Trial Balance / Report Formatting**: Company-specific column ordering, aggregation, and export formats.

When uncertain, stop and ask rather than inventing a business rule.
