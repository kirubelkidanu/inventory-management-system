# Testing Strategy

## Unit tests

Use pytest.

Test:
- quantity validation
- transaction validation
- permission rules
- transfer calculations
- reference validation
- balance calculations

## Integration tests

Test real PostgreSQL behavior for:
- GRV posting
- SIV posting
- ISTV posting
- ISTRV receiving
- SRV
- Adjustment
- audit records

## Critical scenarios

### Scenario 1 — GRV

Start:
0

GRV:
+500

Expected:
500

### Scenario 2 — SIV

Start:
500

SIV:
-100

Expected:
400

### Scenario 3 — ISTV

Start source:
400

Transfer:
100

Expected:
- source = 300
- transit = 100
- destination = unchanged

### Scenario 4 — ISTRV

Transit:
100

Receive:
100

Expected:
- transit = 0
- destination +100

### Scenario 5 — SRV

Stock:
300

Return:
20

Expected:
320

### Scenario 6 — Adjustment

Stock:
320

Adjustment:
-3

Expected:
317

### Scenario 7 — insufficient stock

Stock:
50

Attempt SIV:
100

Expected:
rejected unless client explicitly permits negative stock.

### Scenario 8 — invalid transfer

Source:
WH001

Destination:
WH001

Expected:
rejected.

### Scenario 9 — over-receiving

ISTV remaining:
100

Attempt ISTRV:
150

Expected:
rejected.

### Scenario 10 — duplicate receive

ISTV already fully received.

Attempt another full ISTRV.

Expected:
rejected.

## End-to-end tests

Use Playwright.

Test:
- login
- navigate dashboard
- create GRV
- verify stock
- create SIV
- verify stock
- transfer
- verify transit
- receive
- verify destination
- open Trial Balance
- filter
- open transaction details

## Reconciliation test

Manually calculate a scenario and compare it with the report.

Example:

```text
GRV       +100
SIV        -20
ISTV       -30
ISTRV      +30 at destination
SRV         +5
Adjustment  -2
```

Source/destination balances and total-company stock must reconcile.

## Regression

Every bug fix gets a regression test where practical.

Do not remove a test just because it is inconvenient.

## Definition of done

A feature is done only when:
- implemented
- validated
- tested
- error paths handled
- authorization checked
- UI works
- database migration is committed
- no known critical bug remains
