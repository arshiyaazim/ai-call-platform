# ============================================================
# WBOM — Unified Command Parser
# Parses admin WhatsApp messages into structured commands
# ============================================================
import re
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from database import execute_query, insert_row
from services.fuzzy_search import fuzzy_search_employees, find_employee_fuzzy

logger = logging.getLogger("wbom.command_parser")

# ── Command patterns ──────────────────────────────────────────

COMMAND_PATTERNS = {
    "search": re.compile(
        r"^(?:search|find|khoj|khujo)\s+(.+)",
        re.IGNORECASE,
    ),
    "pay": re.compile(
        r"^(?:pay|send|deo|dao|pathao)\s+(?:tk\.?\s*)?(\d+)\s+(?:to\s+)?(.+?)(?:\s+(?:via|by|from)\s+(bkash|nagad|rocket|cash|bank))?$",
        re.IGNORECASE,
    ),
    "add_employee": re.compile(
        r"^(?:add|new|notun)\s+(?:employee|kormi|karmochari)\s+(.+)",
        re.IGNORECASE,
    ),
    "attendance": re.compile(
        r"^(?:attendance|hajira|uposithi)\s+(.+)",
        re.IGNORECASE,
    ),
    "salary_info": re.compile(
        r"^(?:salary|beton|mash)\s+(?:of\s+)?(.+)",
        re.IGNORECASE,
    ),
    "balance": re.compile(
        r"^(?:balance|baki|hisab)\s+(?:of\s+)?(.+)",
        re.IGNORECASE,
    ),
    "status": re.compile(
        r"^(?:status|info)\s+(?:of\s+)?(.+)",
        re.IGNORECASE,
    ),
    "release": re.compile(
        r"^(?:release|chere dao|khat[ai]m)\s+(.+?)(?:\s+(?:at|from)\s+(.+))?$",
        re.IGNORECASE,
    ),
}


def parse_admin_command(message: str) -> dict:
    """Parse an admin WhatsApp message into a structured command.

    Returns dict with keys: command_type, params, original_message
    """
    message = message.strip()
    if not message:
        return {"command_type": "unknown", "params": {}, "original_message": message}

    for cmd_type, pattern in COMMAND_PATTERNS.items():
        match = pattern.match(message)
        if match:
            return {
                "command_type": cmd_type,
                "params": _extract_params(cmd_type, match),
                "original_message": message,
            }

    # Fallback: check if it looks like a payment message
    if _looks_like_payment(message):
        return {"command_type": "payment_message", "params": {"raw": message}, "original_message": message}

    return {"command_type": "unknown", "params": {"raw": message}, "original_message": message}


def _extract_params(cmd_type: str, match: re.Match) -> dict:
    """Extract parameters from a regex match based on command type."""
    if cmd_type == "search":
        return {"query": match.group(1).strip()}
    elif cmd_type == "pay":
        return {
            "amount": int(match.group(1)),
            "recipient": match.group(2).strip(),
            "method": (match.group(3) or "bkash").capitalize(),
        }
    elif cmd_type == "add_employee":
        return {"details": match.group(1).strip()}
    elif cmd_type == "attendance":
        return {"details": match.group(1).strip()}
    elif cmd_type in ("salary_info", "balance", "status"):
        return {"query": match.group(1).strip()}
    elif cmd_type == "release":
        return {
            "query": match.group(1).strip(),
            "location": match.group(2).strip() if match.group(2) else None,
        }
    return {}


def _looks_like_payment(msg: str) -> bool:
    """Check if message looks like a payment/transaction message."""
    payment_words = {"tk", "taka", "bkash", "nagad", "rocket", "cash", "payment", "advance", "paid"}
    words = set(msg.lower().split())
    return len(words & payment_words) >= 2


def execute_admin_command(parsed: dict) -> dict:
    """Execute a parsed admin command and return result."""
    cmd = parsed["command_type"]
    params = parsed["params"]

    if cmd == "search":
        return _handle_search(params["query"])
    elif cmd == "pay":
        return _handle_pay_draft(params)
    elif cmd == "add_employee":
        return _handle_add_employee(params["details"])
    elif cmd == "attendance":
        return _handle_attendance(params["details"])
    elif cmd == "salary_info":
        return _handle_salary_info(params["query"])
    elif cmd == "balance":
        return _handle_balance(params["query"])
    elif cmd == "status":
        return _handle_status(params["query"])
    elif cmd == "release":
        return _handle_release(params)
    else:
        return {
            "command_type": cmd,
            "result": {},
            "message": "Command not recognized. Available: search, pay, add, attendance, salary, balance, status, release",
            "requires_confirmation": False,
        }


def _handle_search(query: str) -> dict:
    results = fuzzy_search_employees(query, limit=5)
    if not results:
        return {
            "command_type": "search",
            "result": {"matches": []},
            "message": f"No employees found for '{query}'",
            "requires_confirmation": False,
        }
    lines = []
    for r in results:
        bkash = f" B:{r.get('bkash_number', '-')}" if r.get("bkash_number") else ""
        lines.append(
            f"• {r['employee_name']} ({r['designation']}) "
            f"📱{r['employee_mobile']}{bkash} "
            f"[{r['similarity']:.0%}]"
        )
    return {
        "command_type": "search",
        "result": {"matches": results, "count": len(results)},
        "message": f"Found {len(results)} match(es):\n" + "\n".join(lines),
        "requires_confirmation": False,
    }


def _handle_pay_draft(params: dict) -> dict:
    employee = find_employee_fuzzy(params["recipient"])
    if not employee:
        return {
            "command_type": "pay",
            "result": {},
            "message": f"Employee '{params['recipient']}' not found",
            "requires_confirmation": False,
        }

    method = params.get("method", "Bkash")
    amount = params["amount"]

    # Build accountant-ready draft message
    pay_number = employee.get("bkash_number") or employee.get("employee_mobile")
    method_code = "B" if method.lower() == "bkash" else "N" if method.lower() == "nagad" else method[0]

    draft = f"ID: {employee['employee_mobile']} {employee['employee_name']} {pay_number}({method_code}) Tk. {amount}/-"

    return {
        "command_type": "pay",
        "result": {
            "employee_id": employee["employee_id"],
            "employee_name": employee["employee_name"],
            "amount": amount,
            "method": method,
            "draft_message": draft,
        },
        "message": f"💰 Payment draft:\n{draft}\n\nConfirm to record transaction?",
        "requires_confirmation": True,
    }


def _handle_add_employee(details: str) -> dict:
    """Parse: 'Shamim 01812345678 Escort' or similar."""
    parts = details.split()
    if len(parts) < 2:
        return {
            "command_type": "add_employee",
            "result": {},
            "message": "Format: add employee [name] [mobile] [designation]",
            "requires_confirmation": False,
        }

    name = parts[0]
    mobile = None
    designation = "Escort"

    for p in parts[1:]:
        if p.replace("-", "").isdigit() and len(p.replace("-", "")) >= 10:
            mobile = p.replace("-", "")
        elif p.lower() in {"escort", "seal-man", "security", "supervisor", "labor"}:
            designation = p.capitalize()
            if designation == "Security":
                designation = "Security Guard"

    if not mobile:
        return {
            "command_type": "add_employee",
            "result": {},
            "message": "Mobile number is required. Format: add employee [name] [mobile] [designation]",
            "requires_confirmation": False,
        }

    return {
        "command_type": "add_employee",
        "result": {
            "employee_name": name,
            "employee_mobile": mobile,
            "designation": designation,
        },
        "message": f"Add employee: {name} ({designation}) 📱{mobile}\nConfirm?",
        "requires_confirmation": True,
    }


def _handle_attendance(details: str) -> dict:
    """Parse: 'Kamal present' or 'all present today' or 'Rahim absent'."""
    parts = details.lower().split()
    today = date.today().isoformat()

    if parts[0] == "all":
        status = parts[1] if len(parts) > 1 else "present"
        return {
            "command_type": "attendance",
            "result": {"bulk": True, "status": status.capitalize(), "date": today},
            "message": f"Mark all active employees as {status.capitalize()} for {today}?\nConfirm?",
            "requires_confirmation": True,
        }

    name = parts[0]
    status = parts[1].capitalize() if len(parts) > 1 else "Present"
    employee = find_employee_fuzzy(name)
    if not employee:
        return {
            "command_type": "attendance",
            "result": {},
            "message": f"Employee '{name}' not found",
            "requires_confirmation": False,
        }

    return {
        "command_type": "attendance",
        "result": {
            "employee_id": employee["employee_id"],
            "employee_name": employee["employee_name"],
            "status": status,
            "date": today,
        },
        "message": f"Mark {employee['employee_name']} as {status} for {today}?\nConfirm?",
        "requires_confirmation": True,
    }


def _handle_salary_info(query: str) -> dict:
    employee = find_employee_fuzzy(query)
    if not employee:
        return {
            "command_type": "salary_info",
            "result": {},
            "message": f"Employee '{query}' not found",
            "requires_confirmation": False,
        }

    # Get latest salary record
    salary = execute_query(
        "SELECT * FROM wbom_salary_records WHERE employee_id = %s ORDER BY month DESC, year DESC LIMIT 1",
        (employee["employee_id"],),
    )
    # Get running programs count
    programs = execute_query(
        "SELECT COUNT(*) as count FROM wbom_escort_programs WHERE escort_employee_id = %s AND status IN ('Assigned', 'Running')",
        (employee["employee_id"],),
    )
    # Get total advances this month
    advances = execute_query(
        "SELECT COALESCE(SUM(amount), 0) as total FROM wbom_cash_transactions "
        "WHERE employee_id = %s AND transaction_type = 'Advance' AND status = 'Completed' "
        "AND EXTRACT(MONTH FROM transaction_date) = %s AND EXTRACT(YEAR FROM transaction_date) = %s",
        (employee["employee_id"], datetime.now().month, datetime.now().year),
    )

    info = {
        "employee": employee["employee_name"],
        "designation": employee.get("designation"),
        "basic_salary": float(employee.get("basic_salary", 0)),
        "active_programs": programs[0]["count"] if programs else 0,
        "advances_this_month": float(advances[0]["total"]) if advances else 0,
        "last_salary": salary[0] if salary else None,
    }

    msg = (
        f"📊 {employee['employee_name']} ({employee.get('designation', '-')})\n"
        f"Basic: Tk.{info['basic_salary']:.0f}\n"
        f"Active programs: {info['active_programs']}\n"
        f"Advances this month: Tk.{info['advances_this_month']:.0f}"
    )
    return {
        "command_type": "salary_info",
        "result": info,
        "message": msg,
        "requires_confirmation": False,
    }


def _handle_balance(query: str) -> dict:
    employee = find_employee_fuzzy(query)
    if not employee:
        return {
            "command_type": "balance",
            "result": {},
            "message": f"Employee '{query}' not found",
            "requires_confirmation": False,
        }

    # Sum all transactions
    rows = execute_query(
        "SELECT transaction_type, COALESCE(SUM(amount), 0) as total "
        "FROM wbom_cash_transactions "
        "WHERE employee_id = %s AND status = 'Completed' "
        "GROUP BY transaction_type",
        (employee["employee_id"],),
    )
    breakdown = {r["transaction_type"]: float(r["total"]) for r in rows}
    earned = breakdown.get("Salary", 0)
    advances = breakdown.get("Advance", 0)
    food = breakdown.get("Food", 0)
    conveyance = breakdown.get("Conveyance", 0)
    deductions = breakdown.get("Deduction", 0)
    net = earned - advances - food - conveyance - deductions

    msg = (
        f"💰 Balance: {employee['employee_name']}\n"
        f"Salary paid: Tk.{earned:.0f}\n"
        f"Advance: Tk.{advances:.0f}\n"
        f"Food: Tk.{food:.0f} | Conv: Tk.{conveyance:.0f}\n"
        f"Deduction: Tk.{deductions:.0f}\n"
        f"Net: Tk.{net:.0f}"
    )
    return {
        "command_type": "balance",
        "result": {"breakdown": breakdown, "net": net},
        "message": msg,
        "requires_confirmation": False,
    }


def _handle_status(query: str) -> dict:
    employee = find_employee_fuzzy(query)
    if not employee:
        return {
            "command_type": "status",
            "result": {},
            "message": f"Employee '{query}' not found",
            "requires_confirmation": False,
        }

    # Get active programs
    programs = execute_query(
        "SELECT program_id, mother_vessel, lighter_vessel, status, program_date "
        "FROM wbom_escort_programs "
        "WHERE escort_employee_id = %s AND status IN ('Assigned', 'Running') "
        "ORDER BY program_date DESC LIMIT 5",
        (employee["employee_id"],),
    )
    prog_lines = []
    for p in programs:
        prog_lines.append(f"  #{p['program_id']} {p['mother_vessel']}→{p['lighter_vessel']} ({p['status']})")

    msg = (
        f"ℹ️ {employee['employee_name']} ({employee.get('designation', '-')})\n"
        f"Status: {employee.get('status', 'Active')}\n"
        f"Mobile: {employee['employee_mobile']}\n"
        f"Active programs: {len(programs)}"
    )
    if prog_lines:
        msg += "\n" + "\n".join(prog_lines)

    return {
        "command_type": "status",
        "result": {"employee": employee, "programs": programs},
        "message": msg,
        "requires_confirmation": False,
    }


def _handle_release(params: dict) -> dict:
    """Handle program release/completion command."""
    query = params["query"]
    location = params.get("location")

    # Try to find by employee name — get their running program
    employee = find_employee_fuzzy(query)
    if not employee:
        return {
            "command_type": "release",
            "result": {},
            "message": f"Employee '{query}' not found",
            "requires_confirmation": False,
        }

    programs = execute_query(
        "SELECT * FROM wbom_escort_programs "
        "WHERE escort_employee_id = %s AND status IN ('Assigned', 'Running') "
        "ORDER BY program_date DESC LIMIT 1",
        (employee["employee_id"],),
    )
    if not programs:
        return {
            "command_type": "release",
            "result": {},
            "message": f"No active program found for {employee['employee_name']}",
            "requires_confirmation": False,
        }

    prog = programs[0]
    return {
        "command_type": "release",
        "result": {
            "program_id": prog["program_id"],
            "employee_id": employee["employee_id"],
            "employee_name": employee["employee_name"],
            "vessel": f"{prog['mother_vessel']}→{prog['lighter_vessel']}",
            "release_point": location,
        },
        "message": (
            f"Release {employee['employee_name']} from #{prog['program_id']} "
            f"({prog['mother_vessel']}→{prog['lighter_vessel']})"
            + (f" at {location}" if location else "")
            + "\nConfirm?"
        ),
        "requires_confirmation": True,
    }
