# ============================================================
# WBOM — Dashboard Routes  (Sprint-2 D0-01)
# ============================================================
from datetime import date
from typing import Optional

from fastapi import APIRouter, Query

from models import DashboardSummary
from services.dashboard import get_dashboard_summary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    ref_date: Optional[date] = Query(
        None,
        description="Reference date (defaults to today). Format: YYYY-MM-DD.",
    ),
):
    """Owner KPI snapshot: headcount, programs today, payroll status, alerts, cash flow."""
    data = get_dashboard_summary(ref_date=ref_date)
    return DashboardSummary(
        ref_date=data["ref_date"],
        period=data["period"],
        active_employees=data["active_employees"],
        programs_today=data["programs_today"],
        absent_today=data["absent_today"],
        payroll_status=data["payroll_status"],
        alerts=data["alerts"],
        cash_flow=data["cash_flow"],
    )
