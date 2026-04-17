# ============================================================
# WBOM — Accountant Payment Draft Service
# Generates formatted payment draft messages for the accountant
# ============================================================
import logging
from datetime import date
from decimal import Decimal

from database import execute_query

logger = logging.getLogger("wbom.payment_draft")


def generate_payment_draft(employee_id: int, amount: Decimal, payment_method: str = "Bkash",
                           transaction_type: str = "Advance") -> dict:
    """Generate a formatted payment draft message for the accountant.

    Format: "ID: [mobile] [name] [pay_number]([method_code]) Tk. [amount]/-"
    """
    rows = execute_query(
        "SELECT * FROM wbom_employees WHERE employee_id = %s",
        (employee_id,),
    )
    if not rows:
        return {"error": f"Employee {employee_id} not found", "ready_to_send": False}

    emp = rows[0]
    method_lower = payment_method.lower()

    # Determine payment number based on method
    if method_lower == "bkash":
        pay_number = emp.get("bkash_number") or emp["employee_mobile"]
        method_code = "B"
    elif method_lower == "nagad":
        pay_number = emp.get("nagad_number") or emp["employee_mobile"]
        method_code = "N"
    elif method_lower == "rocket":
        pay_number = emp["employee_mobile"]
        method_code = "R"
    elif method_lower == "bank":
        pay_number = emp.get("bank_account") or "N/A"
        method_code = "BK"
    else:
        pay_number = emp["employee_mobile"]
        method_code = "C"

    draft = f"ID: {emp['employee_mobile']} {emp['employee_name']} {pay_number}({method_code}) Tk. {amount}/-"

    return {
        "draft_message": draft,
        "employee": {
            "employee_id": emp["employee_id"],
            "employee_name": emp["employee_name"],
            "employee_mobile": emp["employee_mobile"],
            "bkash_number": emp.get("bkash_number"),
            "nagad_number": emp.get("nagad_number"),
        },
        "amount": float(amount),
        "payment_method": payment_method,
        "transaction_type": transaction_type,
        "ready_to_send": True,
    }


def generate_bulk_salary_drafts(month: int, year: int) -> list[dict]:
    """Generate payment drafts for all employees with salary records for a given month.

    Returns list of draft messages ready to forward to the accountant.
    """
    rows = execute_query(
        "SELECT s.*, e.employee_name, e.employee_mobile, e.bkash_number, e.nagad_number, e.designation "
        "FROM wbom_salary_records s "
        "JOIN wbom_employees e ON s.employee_id = e.employee_id "
        "WHERE s.month = %s AND s.year = %s AND s.status != 'Paid' "
        "ORDER BY e.employee_name",
        (month, year),
    )
    if not rows:
        return []

    drafts = []
    for r in rows:
        net = float(r.get("net_salary", 0))
        if net <= 0:
            continue
        pay_number = r.get("bkash_number") or r["employee_mobile"]
        draft = f"ID: {r['employee_mobile']} {r['employee_name']} {pay_number}(B) Tk. {net:.0f}/-"
        drafts.append({
            "employee_id": r["employee_id"],
            "employee_name": r["employee_name"],
            "net_salary": net,
            "draft_message": draft,
        })

    return drafts


def generate_daily_payment_summary(target_date: date = None) -> dict:
    """Generate a summary of all payments made on a given date."""
    if target_date is None:
        target_date = date.today()

    rows = execute_query(
        "SELECT t.*, e.employee_name, e.designation "
        "FROM wbom_cash_transactions t "
        "JOIN wbom_employees e ON t.employee_id = e.employee_id "
        "WHERE t.transaction_date = %s AND t.status = 'Completed' "
        "ORDER BY t.transaction_type, e.employee_name",
        (target_date,),
    )

    summary = {"date": target_date.isoformat(), "transactions": [], "total": 0, "by_type": {}}
    for r in rows:
        amt = float(r["amount"])
        ttype = r["transaction_type"]
        summary["transactions"].append({
            "employee": r["employee_name"],
            "type": ttype,
            "amount": amt,
            "method": r.get("payment_method", "Cash"),
        })
        summary["total"] += amt
        summary["by_type"][ttype] = summary["by_type"].get(ttype, 0) + amt

    return summary
