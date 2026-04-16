-- ============================================================
-- Migration 012: WBOM Duplicate Prevention & Transaction Safety
-- STEP 2: Unique constraint on cash transactions (employee + date + amount + type)
-- ============================================================

-- Prevent duplicate cash transactions: same employee, same date, same amount, same type, same payment method
-- This catches accidental double-submissions while allowing legitimate same-day multiple transactions of different types/amounts
CREATE UNIQUE INDEX IF NOT EXISTS idx_wbom_transactions_dedup
    ON wbom_cash_transactions (employee_id, transaction_date, amount, transaction_type, payment_method)
    WHERE status = 'Completed';
