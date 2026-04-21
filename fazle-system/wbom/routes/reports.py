# ============================================================
# WBOM — Report Routes
# Phase 7 §7.1: Salary + billing reports
# ============================================================
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from database import execute_query
from models import SalaryReportResponse, BillingReportResponse
from services.salary_generator import (
    calculate_monthly_salary, get_employee_programs, get_employee_transactions,
)

from config import settings as _cfg
from services.wbom_logger import handle_errors

router = APIRouter(prefix="/reports", tags=["reports"])

DEFAULT_SERVICE_CHARGE = _cfg.default_service_charge


@router.get(
    "/salary/{employee_id}/{month}/{year}",
    response_model=SalaryReportResponse,
)
@handle_errors
def salary_report(employee_id: int, month: int, year: int):
    """Generate salary report for an employee."""
    try:
        salary_data = calculate_monthly_salary(employee_id, month, year)
    except ValueError as e:
        raise HTTPException(404, str(e))

    programs = get_employee_programs(employee_id, month, year)
    transactions = get_employee_transactions(employee_id, month, year)

    return SalaryReportResponse(
        salary_summary=salary_data,
        programs=programs,
        transactions=transactions,
    )


@router.get(
    "/billing/{contact_id}",
    response_model=BillingReportResponse,
)
def billing_report(
    contact_id: int,
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD"),
):
    """Generate billing report for a contact."""
    # Default: current month
    if not date_from:
        from datetime import date
        today = date.today()
        date_from = today.replace(day=1).isoformat()
    if not date_to:
        from datetime import date
        date_to = date.today().isoformat()

    programs = execute_query("""
        SELECT * FROM wbom_escort_programs
        WHERE contact_id = %s
          AND status = 'Completed'
          AND program_date BETWEEN %s AND %s
        ORDER BY program_date DESC
    """, (contact_id, date_from, date_to))

    total_programs = len(programs)
    total_amount = total_programs * DEFAULT_SERVICE_CHARGE

    return BillingReportResponse(
        contact_id=contact_id,
        period={"from": date_from, "to": date_to},
        total_programs=total_programs,
        service_charge=DEFAULT_SERVICE_CHARGE,
        total_amount=total_amount,
        programs=programs,
    )


# ── Sprint-2: Daily Activity Report (D0-02) ──────────────────

from models import DailyActivityReport, MonthlyPayrollReport  # noqa: E402
from services.dashboard import get_daily_activity, get_monthly_payroll_report  # noqa: E402


@router.get("/daily", response_model=DailyActivityReport)
def daily_activity_report(
    date: Optional[str] = Query(None, description="YYYY-MM-DD (defaults to today)"),
):
    """Daily operational snapshot: programs, attendance, cash transactions."""
    from datetime import date as _date
    if date:
        ref = _date.fromisoformat(date)
    else:
        ref = _date.today()
    data = get_daily_activity(ref)
    return DailyActivityReport(
        date=data["date"],
        programs=data["programs"],
        attendance=data["attendance"],
        transactions=data["transactions"],
    )


# ── Sprint-2: Monthly Payroll Summary (D0-03) ─────────────────

@router.get("/monthly-payroll", response_model=MonthlyPayrollReport)
def monthly_payroll_report(
    year:  int = Query(..., ge=2020, le=2099, description="4-digit year"),
    month: int = Query(..., ge=1,    le=12,   description="Month 1–12"),
):
    """Monthly payroll run summary: all employee runs, net totals, cash breakdown."""
    data = get_monthly_payroll_report(year, month)
    return MonthlyPayrollReport(
        period=data["period"],
        total_runs=data["total_runs"],
        paid_count=data["paid_count"],
        total_net_salary=data["total_net_salary"],
        cash_summary=data["cash_summary"],
        payroll_runs=data["payroll_runs"],
    )

