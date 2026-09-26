# Inventory Management System

A secure, web-based construction-material inventory management system designed to replace Excel-based tracking with an auditable dual-projection inventory ledger.

## Project Overview

The system maintains real-time stock balances across independent warehouses and construction projects, while enforcing an immutable historical event ledger for every material receipt, issue, transfer, return, and discrepancy adjustment.

### Core Architectural Invariants
1. **Current-State Projection (`inventory_balances`)**: Fast balance lookups, stock availability validation, and deterministic row-level locking (`SELECT ... FOR UPDATE`).
2. **Immutable Event Ledger (`stock_movements`)**: Append-only historical movement ledger. Rows are never modified or deleted.
3. **Atomic Dual-Write**: Every stock-changing transaction updates the balance projection and inserts movement ledger rows within a single database transaction.
4. **Independent Warehouses & Projects**: Warehouses and projects are distinct entities. A warehouse may have an optional default project association, but is not permanently bound to one.
5. **In-Transit Transfer Lifecycle**: `ISTV` decrements source warehouse stock and creates an in-transit transfer record. Destination stock increases only when `ISTRV` is posted.

## Architecture & Technology Stack

- **Frontend**: React, TypeScript, Vite, Tailwind CSS
- **Backend**: Python, FastAPI, SQLAlchemy, Pydantic
- **Database & Auth**: PostgreSQL (Supabase), Supabase Auth
- **Testing & Tooling**: pytest, Playwright, openpyxl, Alembic, Git / GitHub

## Current Status: Day 1 (Foundation)

- **Status**: Foundation & Specification phase.
- **Completed**:
  - Full system specifications and architectural documentation under `docs/`.
  - Repository environment foundation (`.gitignore`, `.env.example`).
- **Implementation Status**: Application source code, database migrations, and package installations have **not yet started**.

## Development Rules

Before modifying business logic or database structure, consult:
- `AGENTS.md`
- `docs/PROJECT_SPEC.md`
- `docs/ARCHITECTURE.md`
- `docs/DATABASE.md`
- `docs/TRANSACTIONS.md`
- `docs/REPORTS.md`
- `docs/SECURITY.md`
- `docs/TESTING.md`
- `docs/15_DAY_PLAN.md`

