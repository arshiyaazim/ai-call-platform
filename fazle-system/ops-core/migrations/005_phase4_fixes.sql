-- Migration 005: Phase 4 schema fixes
-- - Add updated_at column to ops_employees
-- - Widen paid_by column to TEXT (was varchar(20), but names like "Mamun Vai" need TEXT)

BEGIN;

ALTER TABLE ops_employees ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();
ALTER TABLE ops_payments ALTER COLUMN paid_by TYPE TEXT;

COMMIT;
