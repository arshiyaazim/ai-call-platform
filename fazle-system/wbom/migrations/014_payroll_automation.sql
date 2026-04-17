-- ============================================================
-- Migration 014: Full Payroll Automation Schema
-- Adds: attendance table, employee bkash fields, escort lifecycle,
--        conveyance tracking, and self-service columns
-- ============================================================

-- ── Employee enhancements ────────────────────────────────────
ALTER TABLE wbom_employees ADD COLUMN IF NOT EXISTS bkash_number VARCHAR(20);
ALTER TABLE wbom_employees ADD COLUMN IF NOT EXISTS nagad_number VARCHAR(20);
ALTER TABLE wbom_employees ADD COLUMN IF NOT EXISTS basic_salary DECIMAL(10,2) DEFAULT 0;
ALTER TABLE wbom_employees ADD COLUMN IF NOT EXISTS nid_number VARCHAR(20);

-- ── Escort program lifecycle fields ──────────────────────────
ALTER TABLE wbom_escort_programs ADD COLUMN IF NOT EXISTS start_date DATE;
ALTER TABLE wbom_escort_programs ADD COLUMN IF NOT EXISTS end_date DATE;
ALTER TABLE wbom_escort_programs ADD COLUMN IF NOT EXISTS end_shift VARCHAR(1);
ALTER TABLE wbom_escort_programs ADD COLUMN IF NOT EXISTS release_point VARCHAR(100);
ALTER TABLE wbom_escort_programs ADD COLUMN IF NOT EXISTS day_count INT DEFAULT 0;
ALTER TABLE wbom_escort_programs ADD COLUMN IF NOT EXISTS conveyance DECIMAL(10,2) DEFAULT 0;
ALTER TABLE wbom_escort_programs ADD COLUMN IF NOT EXISTS capacity VARCHAR(20);

-- ── Attendance table ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS wbom_attendance (
    attendance_id SERIAL PRIMARY KEY,
    employee_id INT NOT NULL REFERENCES wbom_employees(employee_id),
    attendance_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Present',  -- Present/Absent/Leave/Half-day
    location VARCHAR(100),
    check_in_time TIMESTAMPTZ,
    check_out_time TIMESTAMPTZ,
    remarks TEXT,
    recorded_by VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (employee_id, attendance_date)
);

-- ── Self-service request log ─────────────────────────────────
CREATE TABLE IF NOT EXISTS wbom_employee_requests (
    request_id SERIAL PRIMARY KEY,
    employee_id INT NOT NULL REFERENCES wbom_employees(employee_id),
    request_type VARCHAR(30) NOT NULL,  -- salary_query/advance_request/info_request
    message_body TEXT,
    sender_number VARCHAR(20),
    status VARCHAR(20) DEFAULT 'Pending',  -- Pending/Responded/Delayed/Denied
    response_text TEXT,
    delay_hours INT DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    responded_at TIMESTAMPTZ
);

-- ── Indexes ──────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_wbom_attendance_date ON wbom_attendance(attendance_date);
CREATE INDEX IF NOT EXISTS idx_wbom_attendance_employee ON wbom_attendance(employee_id);
CREATE INDEX IF NOT EXISTS idx_wbom_employee_requests_employee ON wbom_employee_requests(employee_id);
CREATE INDEX IF NOT EXISTS idx_wbom_programs_start_date ON wbom_escort_programs(start_date);
CREATE INDEX IF NOT EXISTS idx_wbom_programs_end_date ON wbom_escort_programs(end_date);
CREATE INDEX IF NOT EXISTS idx_wbom_employees_bkash ON wbom_employees(bkash_number);

-- ── Trigram extension for fuzzy search ───────────────────────
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_wbom_employees_name_trgm ON wbom_employees USING gin (employee_name gin_trgm_ops);
