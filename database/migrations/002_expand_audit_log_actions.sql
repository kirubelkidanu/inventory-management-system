-- Migration 002: Expand audit_logs action check constraint to support transaction-specific verbs
-- In accordance with AGENTS.md Rule 16 (Use migrations)

ALTER TABLE audit_logs DROP CONSTRAINT IF EXISTS audit_logs_action_check;

ALTER TABLE audit_logs ADD CONSTRAINT audit_logs_action_check CHECK (
    action IN (
        'CREATE',
        'UPDATE',
        'POST',
        'CANCEL',
        'CORRECT',
        'IMPORT',
        'DELETE',
        'POST_GRV',
        'POST_SIV',
        'POST_ISTV',
        'POST_ISTRV',
        'POST_SRV',
        'POST_ADJUSTMENT',
        'RECONCILIATION'
    )
);
