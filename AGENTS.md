# AI Coding Agent Instructions

## Role

You are the implementation agent for a real inventory management system.

The project owner and architecture/project manager define business rules. Do not invent business rules when requirements are ambiguous.

## Read first
## Persistent Project Memory

Before starting any implementation task, also read:

- `decisions.md`
- `project_state.md`

These files are the persistent memory of the project.

### `decisions.md`
Contains approved business and architectural decisions.

Rules:
- Treat approved decisions as authoritative.
- Do not contradict an approved decision without explicitly asking the project owner.
- When a new important business or architectural decision is approved, update `decisions.md`.
- Do not invent missing decisions.

### `project_state.md`
Contains the current implementation state of the project.

Rules:
- Read it before beginning work.
- Use it to understand what has already been implemented, tested, or intentionally postponed.
- Do not recreate functionality that already exists.
- After completing a significant task, update `project_state.md` with:
  - what was implemented
  - files changed
  - tests performed
  - current status
  - remaining work
  - important notes/blockers

### Memory Consistency

When `AGENTS.md`, `decisions.md`, `project_state.md`, and the project documentation appear to conflict:

1. Stop.
2. Identify the conflict.
3. Do not silently choose an interpretation.
4. Ask the project owner for clarification.

Never use memory files as permission to invent business rules.

Before changing code, read:
- docs/PROJECT_SPEC.md
- docs/ARCHITECTURE.md
- docs/DATABASE.md
- docs/TRANSACTIONS.md
- docs/REPORTS.md
- docs/SECURITY.md
- docs/TESTING.md
- docs/15_DAY_PLAN.md

## Absolute rules

1. Do not change transaction semantics without approval.
2. Do not invent meanings for GRV, SIV, ISTV, ISTRV, SRV or company-specific fields.
3. Do not hardcode Kazanchis or WH001 into business logic.
4. Do not use fake inventory data when the real imported data is available.
5. Do not expose secrets.
6. Never place service-role/secret keys in frontend code.
7. Never directly overwrite stock quantities from the browser.
8. Every stock change must go through the transaction service.
9. Use database transactions for atomic stock changes.
10. Do not silently delete posted transactions.
11. Do not disable security checks to make a feature work.
12. Do not install unnecessary dependencies.
13. Do not rewrite working architecture without approval.
14. Add tests for stock-changing behavior.
15. Run relevant tests before declaring a task complete.
16. Keep database changes in migrations.
17. Keep business logic out of route handlers.
18. Do not mark a task complete if it only looks correct in the UI.

## Workflow

For each task:

1. Read relevant documentation.
2. State the implementation plan briefly.
3. Inspect existing code.
4. Implement the smallest correct change.
5. Add/update tests.
6. Run tests.
7. Review for security and data integrity.
8. Summarize changed files and test results.

## When requirements are unclear

STOP and ask for clarification.

Do not guess:
- numbering formats
- approval workflows
- negative-stock policy
- partial receiving policy
- adjustment rules
- exact item-code generation
- company-specific report definitions

## Git

Use focused commits.

Examples:
- feat: add GRV transaction workflow
- feat: add SIV stock validation
- feat: add transfer in-transit tracking
- feat: add trial balance report
- test: add transfer reconciliation tests
- fix: prevent over-receiving transfer

Never commit secrets.

## Database

Use migrations.

Never manually modify production schema without a migration.

Important invariants must be protected both in application logic and, where practical, database constraints.

## UI

Prefer clear enterprise forms and tables over decorative UI.

The Trial Balance and transaction history are more important than visual effects.

## Performance

Do not prematurely optimize.

Use indexed queries and pagination for large transaction/report tables.

## Completion

A feature is not complete until:
- implementation exists
- validation exists
- authorization exists where needed
- tests exist
- tests pass
- migration exists if schema changed
- error handling exists
- documentation is updated when behavior changed
