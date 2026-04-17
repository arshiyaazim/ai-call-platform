# ============================================================
# WBOM — Attendance Routes
# ============================================================
from datetime import date
from typing import Optional

from fastapi import APIRouter, Query
from models import AttendanceCreate, AttendanceUpdate, AttendanceResponse
from services.attendance import (
    record_attendance,
    bulk_mark_attendance,
    get_attendance_report,
    get_monthly_summary,
)

router = APIRouter(prefix="/attendance", tags=["Attendance"])


@router.post("/", response_model=dict)
async def create_attendance(req: AttendanceCreate):
    """Record attendance for an employee."""
    result = record_attendance(
        employee_id=req.employee_id,
        attendance_date=req.attendance_date,
        status=req.status,
        location=req.location,
        check_in_time=req.check_in_time,
        check_out_time=req.check_out_time,
        remarks=req.remarks,
        recorded_by=req.recorded_by,
    )
    return result


@router.post("/bulk", response_model=dict)
async def bulk_attendance(
    status: str = "Present",
    attendance_date: Optional[date] = None,
    recorded_by: Optional[str] = None,
):
    """Mark all active employees with a given status."""
    return bulk_mark_attendance(status=status, attendance_date=attendance_date, recorded_by=recorded_by)


@router.get("/report", response_model=list)
async def attendance_report(
    attendance_date: Optional[date] = Query(None),
    employee_id: Optional[int] = Query(None),
):
    """Get attendance report with optional filters."""
    return get_attendance_report(attendance_date=attendance_date, employee_id=employee_id)


@router.get("/monthly-summary/{employee_id}", response_model=dict)
async def monthly_summary(employee_id: int, month: int = Query(...), year: int = Query(...)):
    """Get monthly attendance summary for an employee."""
    return get_monthly_summary(employee_id=employee_id, month=month, year=year)
