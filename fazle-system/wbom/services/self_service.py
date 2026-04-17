# ============================================================
# WBOM — Employee Self-Service
# Handles incoming employee messages for salary queries,
# advance requests, and general info
# ============================================================
import logging
from datetime import datetime

from database import execute_query, insert_record

logger = logging.getLogger("wbom.self_service")


def identify_employee_by_mobile(mobile: str) -> dict | None:
    """Find employee by mobile number (exact or with leading zero toggle)."""
    mobile = mobile.replace("-", "").replace(" ", "").replace("+880", "0")
    if not mobile.startswith("0") and len(mobile) == 10:
        mobile = "0" + mobile

    rows = execute_query(
        "SELECT * FROM wbom_employees WHERE employee_mobile = %s OR employee_mobile = %s LIMIT 1",
        (mobile, mobile.lstrip("0")),
    )
    return rows[0] if rows else None


def process_employee_message(sender_number: str, message_body: str) -> dict:
    """Process an incoming message from an employee.

    Identifies the employee, classifies their request,
    and generates an appropriate response or logs the request.
    """
    employee = identify_employee_by_mobile(sender_number)
    if not employee:
        return {
            "recognized": False,
            "response": "Could not identify employee. Please contact admin.",
            "request_logged": False,
        }

    eid = employee["employee_id"]
    msg_lower = message_body.lower()

    # Classify request type
    if any(w in msg_lower for w in ["salary", "beton", "mash", "pagar", "pagla"]):
        return _handle_salary_query(employee)
    elif any(w in msg_lower for w in ["advance", "agrim", "dhaar", "loan"]):
        return _handle_advance_request(employee, message_body)
    elif any(w in msg_lower for w in ["program", "duty", "schedule", "roster"]):
        return _handle_program_query(employee)
    else:
        # Log as general info request
        _log_request(eid, "info_request", message_body, sender_number)
        return {
            "recognized": True,
            "employee_name": employee["employee_name"],
            "response": f"Your message has been received, {employee['employee_name']}. Admin will respond shortly.",
            "request_logged": True,
        }


def _handle_salary_query(employee: dict) -> dict:
    """Handle salary query from employee — return basic salary info."""
    eid = employee["employee_id"]
    now = datetime.now()

    # Get this month's advances
    advances = execute_query(
        "SELECT COALESCE(SUM(amount), 0) as total FROM wbom_cash_transactions "
        "WHERE employee_id = %s AND transaction_type = 'Advance' AND status = 'Completed' "
        "AND EXTRACT(MONTH FROM transaction_date) = %s AND EXTRACT(YEAR FROM transaction_date) = %s",
        (eid, now.month, now.year),
    )

    # Get completed programs this month
    programs = execute_query(
        "SELECT COUNT(*) as count FROM wbom_escort_programs "
        "WHERE escort_employee_id = %s AND status = 'Completed' "
        "AND EXTRACT(MONTH FROM program_date) = %s AND EXTRACT(YEAR FROM program_date) = %s",
        (eid, now.month, now.year),
    )

    advance_total = float(advances[0]["total"]) if advances else 0
    program_count = programs[0]["count"] if programs else 0

    _log_request(eid, "salary_query", "Auto-responded", employee["employee_mobile"])

    return {
        "recognized": True,
        "employee_name": employee["employee_name"],
        "response": (
            f"{employee['employee_name']}, this month:\n"
            f"Programs completed: {program_count}\n"
            f"Advances taken: Tk.{advance_total:.0f}\n"
            f"For detailed salary info, please contact admin."
        ),
        "request_logged": True,
        "data": {
            "programs_completed": program_count,
            "advances_taken": advance_total,
        },
    }


def _handle_advance_request(employee: dict, message_body: str) -> dict:
    """Log advance request — requires admin approval."""
    eid = employee["employee_id"]

    _log_request(eid, "advance_request", message_body, employee["employee_mobile"])

    return {
        "recognized": True,
        "employee_name": employee["employee_name"],
        "response": (
            f"{employee['employee_name']}, your advance request has been forwarded to admin. "
            f"Please wait for approval."
        ),
        "request_logged": True,
        "requires_admin_action": True,
    }


def _handle_program_query(employee: dict) -> dict:
    """Return active program info for the employee."""
    eid = employee["employee_id"]

    programs = execute_query(
        "SELECT program_id, mother_vessel, lighter_vessel, status, program_date, shift "
        "FROM wbom_escort_programs "
        "WHERE escort_employee_id = %s AND status IN ('Assigned', 'Running') "
        "ORDER BY program_date DESC LIMIT 5",
        (eid,),
    )

    if not programs:
        response = f"{employee['employee_name']}, you have no active programs currently."
    else:
        lines = [f"{employee['employee_name']}, your active programs:"]
        for p in programs:
            lines.append(
                f"  #{p['program_id']} {p['mother_vessel']}→{p['lighter_vessel']} "
                f"({p['status']}) {p['program_date']} {p['shift']}"
            )
        response = "\n".join(lines)

    _log_request(eid, "info_request", "Program query - auto-responded", employee["employee_mobile"])

    return {
        "recognized": True,
        "employee_name": employee["employee_name"],
        "response": response,
        "request_logged": True,
        "data": {"programs": programs},
    }


def _log_request(employee_id: int, request_type: str, message_body: str, sender_number: str):
    """Log employee request to the database."""
    try:
        insert_record("wbom_employee_requests", {
            "employee_id": employee_id,
            "request_type": request_type,
            "message_body": message_body,
            "sender_number": sender_number,
            "status": "Pending",
        })
    except Exception as e:
        logger.error("Failed to log employee request: %s", e)


def get_pending_requests(limit: int = 50) -> list[dict]:
    """Get all pending employee requests for admin review."""
    return execute_query(
        "SELECT r.*, e.employee_name, e.designation, e.employee_mobile "
        "FROM wbom_employee_requests r "
        "JOIN wbom_employees e ON r.employee_id = e.employee_id "
        "WHERE r.status = 'Pending' "
        "ORDER BY r.created_at DESC LIMIT %s",
        (limit,),
    )


def respond_to_request(request_id: int, response_text: str, status: str = "Responded") -> dict:
    """Admin responds to an employee request."""
    rows = execute_query(
        "UPDATE wbom_employee_requests SET response_text = %s, status = %s, responded_at = NOW() "
        "WHERE request_id = %s RETURNING *",
        (response_text, status, request_id),
    )
    if rows:
        return {"success": True, "request": rows[0]}
    return {"success": False, "error": "Request not found"}
