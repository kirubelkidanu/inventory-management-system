# Transaction Rules

## General rules

Every transaction:
- has a unique transaction number.
- has a transaction date.
- has a transaction type.
- has one or more lines.
- records creator and timestamps.
- creates stock movements only when posted/approved according to the agreed workflow.
- is auditable.

## GRV (Goods Receiving Voucher)

Flow:

```text
Supplier/material arrival
        |
       GRV (Record Store No, Supplier, Received GRV No, Invoice No)
        |
       IN
        |
Warehouse stock increases
```

Validation & Document Fields:
- warehouse / store location required
- project required if the warehouse/project model requires it
- supplier name / received GRV number / invoice number recorded
- at least one item line
- positive quantities
- valid item code and matching unit of measure
- *(Note: Physical GRV shows Unit Price & Total Price; pending client confirmation before integrating pricing)*

## SIV (Store Issue Voucher)

Flow:

```text
Request/Requisition (Requested From, Dept/Project, Requested No)
    |
   SIV (Issued By, Checked By, Received By, Approved By)
    |
   OUT
    |
Warehouse stock decreases
```

Validation & Document Fields:
- warehouse / store location required
- item available
- sufficient stock unless negative stock is explicitly approved
- requisition details recorded (`requested_from`, `project_dept`, `requested_no`, `siv_no`)
- signatory fields captured (`issued_by`, `checked_by`, `received_by`, `approved_by`)

## ISTV (Inter-Store Transfer Voucher)

Flow:

```text
Source WH (FROM)
   |
 ISTV (Record TO, Plate No, Driver Name, ISTV No)
   |
OUT from Source
   |
IN TRANSIT (Assigned to Vehicle/Driver)
```

Validation & Document Fields:
- source warehouse (FROM) required
- destination warehouse (TO) required
- source != destination
- transport accountability recorded (`plate_no`, `driver_name`, `istv_no`)
- sufficient stock in source warehouse
- valid lines with positive quantities

The source stock decreases and transit balance increases when the ISTV is posted.

## ISTRV

Flow:

```text
ISTV
  |
IN TRANSIT
  |
ISTRV
  |
Destination stock IN
```

Validation:
- valid ISTV reference
- destination matches the transfer destination
- received quantity <= remaining quantity
- duplicate completion prevented

## SRV

Flow:

```text
Previous SIV
    |
   SRV
    |
    IN
```

Validation:
- original SIV reference where required
- return quantity follows client rule
- accepted quantity is positive

## ADJUSTMENT

Flow:

```text
Physical count
     |
Discrepancy
     |
Adjustment
     |
IN / OUT
```

Requirements:
- reason mandatory
- privileged role
- audit log mandatory
- before/after quantities visible

## Transaction editing

Preferred:
- Draft transactions may be edited freely by permitted users.
- Posted transactions should not be silently overwritten.
- Corrections must be audited.
- If business workflow requires cancellation, use a cancellation/reversal mechanism rather than deleting history.

## Numbering

The exact numbering scheme is not yet confirmed. Do not invent it.

Possible examples only:
- GRV-000001
- SIV-000001
- ISTV-000001
- ISTRV-000001
- SRV-000001

These are placeholders until the client confirms the required format.

## Atomicity

Each posting operation must be atomic.

GRV:
- create transaction
- create lines
- create movements
- update/recalculate balance
- audit

All in one database transaction.

ISTV:
- create transaction
- create lines
- decrease source stock
- create in-transit quantities
- create transfer record
- audit

All in one database transaction.
