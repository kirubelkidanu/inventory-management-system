# 15-Day Execution Plan

## Day 1 — Foundation

- Initialize Git repository
- Create branches
- Set up frontend
- Set up backend
- Set up Supabase
- Configure environment variables
- Create initial migrations
- Create README/AGENTS rules

Deliverable:
Application starts locally and connects to the development database.

## Day 2 — Master Data

- Categories (14 verified major categories)
- Subcategories (with handling for unpopulated spare part subcategories)
- Items (5,646 real items across 14 active sheets)
- Projects & Warehouses
- UOM Normalization & Validation (including resolution of 569 Steel items with blank UOMs)
- Excel import script (validation, duplicate checks, dry-run mode)

Deliverable:
Authoritative 5,646 client item master loaded and browseable in the application.

## Day 3 — GRV

- GRV UI & API supporting physical voucher fields (Store Location, Supplier, Received GRV No, Invoice No)
- validation (positive quantities, item & UOM match)
- stock IN movement
- transaction history
- tests

Deliverable:
Receiving stock with physical voucher reference tracking changes inventory correctly.

## Day 4 — SIV

- SIV UI & API supporting requisition and signatory fields (`requested_from`, `project_dept`, `requested_no`, `siv_no`, `issued_by`, `checked_by`, `received_by`, `approved_by`)
- stock availability validation
- OUT movement
- tests

Deliverable:
Issuing stock with multi-party requisition audit works safely.

## Day 5 — ISTV

- Transfer UI & API supporting logistics tracking (`FROM`, `TO`, `Plate No`, `Driver Name`, `ISTV No`)
- source/destination validation (source != destination)
- OUT movement from source
- in-transit record creation linked to vehicle plate and driver
- tests

Deliverable:
Transfer creates correct source OUT and verifiable in-transit state.

## Day 6 — ISTRV

- receive transfer UI & API
- reference validation against originating ISTV
- destination IN
- in-transit completion
- tests

Deliverable:
Transfers can be received and reconciled against in-transit driver/vehicle records.

## Day 7 — SRV + Adjustment

- SRV
- SIV reference
- adjustment
- reason
- authorization
- audit

Deliverable:
Returns and controlled adjustments work.

## Day 8 — Stock Balance

- warehouse balance
- project balance
- item balance
- category filters

Deliverable:
Current stock can be trusted and reconciled.

## Day 9 — Trial Balance

- detailed movement query
- filters
- running balance
- transaction links

Deliverable:
Primary client report works.

## Day 10 — Lookup

- item lookup
- transaction lookup
- reference lookup
- item history
- in-transit lookup

Deliverable:
Users can trace inventory movements.

## Day 11 — Roles/Security

- roles
- permissions
- backend authorization
- RLS review
- secret review
- audit

Deliverable:
Unauthorized stock changes are blocked.

## Day 12 — Editing/Correction

- draft editing
- controlled posted correction
- audit history
- correction reason

Deliverable:
Historical data is protected.

## Day 13 — UI/UX

- dashboard
- navigation
- responsive layouts
- loading/error states
- form validation
- table usability

Deliverable:
Client-ready interface.

## Day 14 — Testing/Reconciliation

- integration tests
- Playwright tests
- transaction scenarios
- Excel reconciliation
- fix critical bugs

Deliverable:
Core inventory calculations match expected results.

## Day 15 — Client demo

- backup
- deployment
- final smoke tests
- sample workflow
- client walkthrough
- collect feedback
- document known limitations

Deliverable:
Controlled MVP demonstration/initial deployment.

## Scope rule

If a feature threatens the core inventory ledger or Trial Balance deadline, defer non-essential features rather than weakening transaction correctness.
