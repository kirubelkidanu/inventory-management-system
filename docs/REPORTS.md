# Reports

## Priority 1 — Trial Balance / Detailed Inventory Movement

This is the most required report.

The report must answer:
- What item?
- How much?
- Which warehouse?
- Which project?
- IN or OUT?
- Which transaction?
- Which reference?
- When?
- Who?
- What is the resulting balance?

Columns:
- Date
- Transaction Number
- Transaction Type
- Reference / Document No (e.g. Invoice No, SIV Requisition No, Physical GRV/ISTV/SIV No)
- Inventory ID (e.g. `01-CM-00001`, `02-ST-00001`, `14-TY-00001`)
- Description
- Main Category
- Subcategory
- Unit
- Warehouse Code
- Warehouse Name
- Project / Dept
- Transport Info (Plate No, Driver Name for transfers)
- IN
- OUT
- Running Balance
- Status
- Entered By / Authorized By
- Created At

Filters:
- Date range
- Item
- Category
- Warehouse
- Project / Dept
- Transaction type
- Reference / Invoice / Voucher No
- Plate No / Driver Name
- Status

Actions:
- Open transaction
- Lookup item
- Export Excel
- Print
- PDF later if time permits

## Stock Balance

Shows current quantity grouped by:
- warehouse
- project
- item
- category

Example:

```text
Warehouse: WH001
Project: Kazanchis

Item ID        Description      Unit    Available
01-CM-00001   Cement PLC        Qtl     500
```

## In Transit

Shows:
- ISTV number / Physical ISTV No
- Date
- Source Warehouse (FROM)
- Destination Warehouse (TO)
- Project / Dept
- Vehicle Plate No
- Driver Name
- Item ID & Description
- Sent Quantity
- Received Quantity
- Remaining Quantity
- Status

## Item History

Given an item, show all movements in chronological order.

## Transaction Lookup

Search:
- Transaction number / Voucher number (GRV No, SIV No, ISTV No)
- Reference / Invoice number / Requisition number
- Vehicle Plate number / Driver name
- Item ID / Description
- Warehouse
- Project
- Type
- Date range

## Export

Excel export is higher priority than PDF in the 15-day MVP.

Never export data from a manually reconstructed frontend table if a server-side report query is available. The report should be generated from authoritative database data.
