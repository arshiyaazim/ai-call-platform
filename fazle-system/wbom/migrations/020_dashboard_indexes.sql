-- ============================================================
-- 020: WBOM Owner Dashboard & Reports — Performance Indexes
-- Sprint-2  D0-01 / D0-02 / D0-03
--
-- Adds covering indexes required by:
--   D0-01  GET /dashboard/summary
--   D0-02  GET /reports/daily?date=
--   D0-03  GET /reports/monthly-payroll?year=&month=
--
-- Pure index additions — no table structures are changed.
-- All statements are idempotent (CREATE INDEX IF NOT EXISTS).
-- ============================================================

-- ── wbom_escort_programs ─────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_programs_date
    ON wbom_escort_programs (program_date);

CREATE INDEX IF NOT EXISTS idx_programs_status_date
    ON wbom_escort_programs (status, program_date);

-- ── wbom_cash_transactions ────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_tx_date
    ON wbom_cash_transactions (transaction_date);

CREATE INDEX IF NOT EXISTS idx_tx_type_date
    ON wbom_cash_transactions (transaction_type, transaction_date);

-- ── wbom_payroll_runs ─────────────────────────────────────────
-- idx_payroll_runs_period already created by migration 019
-- Additional covering index for overdue-alert query
CREATE INDEX IF NOT EXISTS idx_payroll_runs_payout_target
    ON wbom_payroll_runs (payout_target_date)
    WHERE status IN ('draft', 'reviewed', 'approved', 'locked');

-- ── wbom_attendance ───────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_attendance_date
    ON wbom_attendance (attendance_date);

CREATE INDEX IF NOT EXISTS idx_attendance_status_date
    ON wbom_attendance (status, attendance_date);

-- ── wbom_employees ────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_employees_status
    ON wbom_employees (status);
