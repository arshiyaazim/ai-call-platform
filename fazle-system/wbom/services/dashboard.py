# ============================================================
# WBOM — Dashboard Service  (Sprint-2 D0-01)
# Owner KPI summary — aggregated read-only queries.
# All queries are safe to re-run at any time (no writes).
# ============================================================
from __future__ import annotations

import logging
from datetime import date

from database import execute_query

logger = logging.getLogger("wbom.dashboard")


def get_dashboard_summary(ref_date: date | None = None) -> dict:
    """Return owner KPI snapshot.

    Parameters
    ----------
    ref_date : date | None
        Reference date for "today" queries.  Defaults to ``date.today()``.
        Exposed as a parameter so tests can inject a deterministic date.
    """
    today = ref_date or date.today()
    year = today.year
    month = today.month

    # ── 1. Headcount ─────────────────────────────────────────
    rows = execute_query(
        "SELECT COUNT(*) AS cnt FROM wbom_employees WHERE status = 'Active'",
        (),
    )
    active_employees: int = int(rows[0]["cnt"]) if rows else 0

    # ── 2. Programs today ────────────────────────────────────
    rows = execute_query(
        """
        SELECT COUNT(*) AS cnt
        FROM wbom_escort_programs
        WHERE program_date = %s
          AND status IN ('Assigned', 'Running')
        """,
        (str(today),),
    )
    programs_today: int = int(rows[0]["cnt"]) if rows else 0

    # ── 3. Absent today ──────────────────────────────────────
    rows = execute_query(
        """
        SELECT COUNT(*) AS cnt
        FROM wbom_attendance
        WHERE attendance_date = %s
          AND status = 'Absent'
        """,
        (str(today),),
    )
    absent_today: int = int(rows[0]["cnt"]) if rows else 0

    # ── 4. Payroll status counts (current period) ────────────
    rows = execute_query(
        """
        SELECT status, COUNT(*) AS cnt
        FROM wbom_payroll_runs
        WHERE period_year  = %s
          AND period_month = %s
        GROUP BY status
        """,
        (year, month),
    )
    payroll_counts: dict[str, int] = {r["status"]: int(r["cnt"]) for r in rows}
    payroll_status = {
        "draft":    payroll_counts.get("draft",    0),
        "reviewed": payroll_counts.get("reviewed", 0),
        "approved": payroll_counts.get("approved", 0),
        "locked":   payroll_counts.get("locked",   0),
        "paid":     payroll_counts.get("paid",      0),
    }

    # ── 5. Overdue payroll alerts ─────────────────────────────
    rows = execute_query(
        """
        SELECT COUNT(*) AS cnt
        FROM wbom_payroll_runs
        WHERE status IN ('draft', 'reviewed', 'approved', 'locked')
          AND payout_target_date IS NOT NULL
          AND payout_target_date < %s
        """,
        (str(today),),
    )
    overdue_payroll: int = int(rows[0]["cnt"]) if rows else 0

    # ── 6. Unpaid-advance alert ───────────────────────────────
    # Employees who have a net advance (Advance > Salary credits) but no
    # 'paid' payroll run this month.
    rows = execute_query(
        """
        SELECT COUNT(*) AS cnt
        FROM wbom_employees e
        WHERE e.status = 'Active'
          AND NOT EXISTS (
              SELECT 1 FROM wbom_payroll_runs pr
              WHERE pr.employee_id  = e.employee_id
                AND pr.period_year  = %s
                AND pr.period_month = %s
                AND pr.status       = 'paid'
          )
          AND (
              SELECT COALESCE(SUM(t.amount), 0)
              FROM wbom_cash_transactions t
              WHERE t.employee_id      = e.employee_id
                AND t.transaction_type = 'Advance'
                AND t.status           = 'Completed'
          ) > 0
        """,
        (year, month),
    )
    unpaid_advance_count: int = int(rows[0]["cnt"]) if rows else 0

    # ── 7. Cash flow this month ───────────────────────────────
    rows = execute_query(
        """
        SELECT
            COALESCE(SUM(CASE WHEN transaction_type = 'Advance'    THEN amount ELSE 0 END), 0) AS total_advances,
            COALESCE(SUM(CASE WHEN transaction_type = 'Deduction'  THEN amount ELSE 0 END), 0) AS total_deductions,
            COALESCE(SUM(CASE WHEN transaction_type = 'Salary'     THEN amount ELSE 0 END), 0) AS total_salary_out,
            COALESCE(SUM(CASE WHEN transaction_type IN ('Food','Conveyance','Other') THEN amount ELSE 0 END), 0) AS total_other
        FROM wbom_cash_transactions
        WHERE EXTRACT(YEAR  FROM transaction_date) = %s
          AND EXTRACT(MONTH FROM transaction_date) = %s
          AND status = 'Completed'
        """,
        (year, month),
    )
    cash_row = rows[0] if rows else {}

    return {
        "ref_date": str(today),
        "period": {"year": year, "month": month},
        "active_employees": active_employees,
        "programs_today":   programs_today,
        "absent_today":     absent_today,
        "payroll_status":   payroll_status,
        "alerts": {
            "overdue_payroll":    overdue_payroll,
            "unpaid_advance":     unpaid_advance_count,
        },
        "cash_flow": {
            "total_advances":    float(cash_row.get("total_advances",   0) or 0),
            "total_deductions":  float(cash_row.get("total_deductions", 0) or 0),
            "total_salary_out":  float(cash_row.get("total_salary_out", 0) or 0),
            "total_other":       float(cash_row.get("total_other",      0) or 0),
        },
    }


def get_daily_activity(ref_date: date) -> dict:
    """Return operational snapshot for a single day.  (D0-02)"""

    # Programs on the day
    programs = execute_query(
        """
        SELECT p.program_id, p.mother_vessel, p.lighter_vessel,
               p.program_date, p.shift, p.status,
               e.employee_name AS escort_name
        FROM wbom_escort_programs p
        LEFT JOIN wbom_employees e ON e.employee_id = p.escort_employee_id
        WHERE p.program_date = %s
        ORDER BY p.shift, p.program_id
        """,
        (str(ref_date),),
    )

    # Attendance on the day
    attendance = execute_query(
        """
        SELECT a.attendance_id, a.employee_id, e.employee_name,
               a.status, a.check_in_time, a.check_out_time, a.location
        FROM wbom_attendance a
        JOIN wbom_employees e ON e.employee_id = a.employee_id
        WHERE a.attendance_date = %s
        ORDER BY e.employee_name
        """,
        (str(ref_date),),
    )

    # Transactions on the day
    transactions = execute_query(
        """
        SELECT t.transaction_id, t.employee_id, e.employee_name,
               t.transaction_type, t.amount, t.payment_method, t.status, t.remarks
        FROM wbom_cash_transactions t
        JOIN wbom_employees e ON e.employee_id = t.employee_id
        WHERE t.transaction_date = %s
        ORDER BY t.transaction_id
        """,
        (str(ref_date),),
    )

    present = sum(1 for a in attendance if a.get("status") == "Present")
    absent  = sum(1 for a in attendance if a.get("status") == "Absent")

    return {
        "date":       str(ref_date),
        "programs":   [dict(r) for r in programs],
        "attendance": {
            "present": present,
            "absent":  absent,
            "records": [dict(r) for r in attendance],
        },
        "transactions": [dict(r) for r in transactions],
    }


def get_monthly_payroll_report(year: int, month: int) -> dict:
    """Return full payroll run summary for a month.  (D0-03)"""

    rows = execute_query(
        """
        SELECT
            pr.run_id,
            pr.employee_id,
            e.employee_name,
            e.designation,
            pr.status,
            pr.basic_salary,
            pr.total_programs,
            pr.program_allowance,
            pr.other_allowance,
            pr.total_advances,
            pr.total_deductions,
            pr.gross_salary,
            pr.net_salary,
            pr.payout_target_date,
            pr.payment_method,
            pr.paid_at
        FROM wbom_payroll_runs pr
        JOIN wbom_employees e ON e.employee_id = pr.employee_id
        WHERE pr.period_year  = %s
          AND pr.period_month = %s
        ORDER BY e.employee_name
        """,
        (year, month),
    )

    # Cash summary
    cash_rows = execute_query(
        """
        SELECT
            COALESCE(SUM(CASE WHEN transaction_type = 'Advance'   THEN amount ELSE 0 END), 0) AS total_advances,
            COALESCE(SUM(CASE WHEN transaction_type = 'Deduction' THEN amount ELSE 0 END), 0) AS total_deductions,
            COALESCE(SUM(CASE WHEN transaction_type = 'Salary'    THEN amount ELSE 0 END), 0) AS total_salary_out
        FROM wbom_cash_transactions
        WHERE EXTRACT(YEAR  FROM transaction_date) = %s
          AND EXTRACT(MONTH FROM transaction_date) = %s
          AND status = 'Completed'
        """,
        (year, month),
    )
    cash = cash_rows[0] if cash_rows else {}

    payroll_rows = [dict(r) for r in rows]
    total_net = sum(float(r.get("net_salary") or 0) for r in payroll_rows)
    paid_count = sum(1 for r in payroll_rows if r.get("status") == "paid")

    return {
        "period":     {"year": year, "month": month},
        "total_runs": len(payroll_rows),
        "paid_count": paid_count,
        "total_net_salary": total_net,
        "cash_summary": {
            "total_advances":   float(cash.get("total_advances",   0) or 0),
            "total_deductions": float(cash.get("total_deductions", 0) or 0),
            "total_salary_out": float(cash.get("total_salary_out", 0) or 0),
        },
        "payroll_runs": payroll_rows,
    }
