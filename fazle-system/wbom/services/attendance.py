# ============================================================
# WBOM — Attendance Service
# Daily attendance tracking for employees
# ============================================================
import logging
from datetime import date, datetime

from database import execute_query, insert_row

logger = logging.getLogger("wbom.attendance")


def record_attendance(employee_id: int, attendance_date: date, status: str = "Present",
                      location: str = None, check_in_time: datetime = None,
                      check_out_time: datetime = None, remarks: str = None,
                      recorded_by: str = None) -> dict:
    """Record or update attendance for an employee on a given date.

    Uses UPSERT: if attendance already exists for that employee+date, updates it.
    """
    existing = execute_query(
        "SELECT attendance_id FROM wbom_attendance "
        "WHERE employee_id = %s AND attendance_date = %s",
        (employee_id, attendance_date),
    )

    if existing:
        # Update existing record
        sets = ["status = %s"]
        vals = [status]
        if location is not None:
            sets.append("location = %s")
            vals.append(location)
        if check_in_time is not None:
            sets.append("check_in_time = %s")
            vals.append(check_in_time)
        if check_out_time is not None:
            sets.append("check_out_time = %s")
            vals.append(check_out_time)
        if remarks is not None:
            sets.append("remarks = %s")
            vals.append(remarks)

        vals.append(existing[0]["attendance_id"])
        execute_query(
            f"UPDATE wbom_attendance SET {', '.join(sets)} WHERE attendance_id = %s RETURNING *",
            tuple(vals),
        )
        logger.info("Updated attendance %s for employee %s", existing[0]["attendance_id"], employee_id)
        return {"action": "updated", "attendance_id": existing[0]["attendance_id"]}
    else:
        record = insert_row("wbom_attendance", {
            "employee_id": employee_id,
            "attendance_date": attendance_date,
            "status": status,
            "location": location,
            "check_in_time": check_in_time,
            "check_out_time": check_out_time,
            "remarks": remarks,
            "recorded_by": recorded_by,
        })
        logger.info("Created attendance for employee %s on %s", employee_id, attendance_date)
        return {"action": "created", "attendance_id": record.get("attendance_id") if record else None}


def bulk_mark_attendance(status: str = "Present", attendance_date: date = None,
                         recorded_by: str = None) -> dict:
    """Mark all active employees as present/absent for a given date."""
    if attendance_date is None:
        attendance_date = date.today()

    employees = execute_query(
        "SELECT employee_id FROM wbom_employees WHERE status = 'Active'",
    )
    results = {"marked": 0, "skipped": 0, "date": attendance_date.isoformat()}
    for emp in employees:
        result = record_attendance(
            employee_id=emp["employee_id"],
            attendance_date=attendance_date,
            status=status,
            recorded_by=recorded_by,
        )
        if result["action"] == "created":
            results["marked"] += 1
        else:
            results["skipped"] += 1

    return results


def get_attendance_report(attendance_date: date = None, employee_id: int = None) -> list[dict]:
    """Get attendance records with optional date/employee filters."""
    conditions = []
    params = []

    if attendance_date:
        conditions.append("a.attendance_date = %s")
        params.append(attendance_date)
    if employee_id:
        conditions.append("a.employee_id = %s")
        params.append(employee_id)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    return execute_query(
        f"SELECT a.*, e.employee_name, e.designation, e.employee_mobile "
        f"FROM wbom_attendance a "
        f"JOIN wbom_employees e ON a.employee_id = e.employee_id "
        f"{where} "
        f"ORDER BY a.attendance_date DESC, e.employee_name "
        f"LIMIT 200",
        tuple(params) if params else None,
    )


def get_monthly_summary(employee_id: int, month: int, year: int) -> dict:
    """Get monthly attendance summary for an employee."""
    rows = execute_query(
        "SELECT status, COUNT(*) as count FROM wbom_attendance "
        "WHERE employee_id = %s AND EXTRACT(MONTH FROM attendance_date) = %s "
        "AND EXTRACT(YEAR FROM attendance_date) = %s "
        "GROUP BY status",
        (employee_id, month, year),
    )
    summary = {r["status"]: r["count"] for r in rows}
    summary["total_days"] = sum(summary.values())
    return summary
