#!/usr/bin/env python3
"""
Phase 4 CSV Import Script — Payments, Employees, Contacts
Runs inside the ai-postgres container via docker exec.
ALL rows inserted, no duplicate removal.
"""

import csv
import io
import re
import sys
import json
from datetime import datetime


def normalize_mobile(raw: str) -> str:
    """Normalize mobile number to 01XXXXXXXXX (11 digits, leading zero)."""
    if not raw:
        return ""
    p = raw.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    p = p.lstrip("+")
    # Remove country code
    if p.startswith("880") and len(p) >= 13:
        p = "0" + p[3:]
    elif p.startswith("88") and len(p) >= 12:
        p = "0" + p[2:]
    # Ensure leading zero
    if len(p) == 10 and p[0] in "123456789":
        p = "0" + p
    # Validate
    if re.match(r"^01\d{9}$", p):
        return p
    return ""


def parse_amount(raw: str) -> int:
    """Parse amount string like '1,520.00' or '200' to integer."""
    if not raw:
        return 0
    cleaned = raw.strip().replace(",", "").replace(" ", "")
    try:
        return int(float(cleaned))
    except ValueError:
        return 0


def map_method(raw: str) -> str:
    """Map CSV method to B (Bkash) or N (Nagad). Unknown → NULL."""
    if not raw:
        return ""
    m = raw.strip().lower()
    if m in ("b", "bkash", "bk", "বিকাশ"):
        return "B"
    if m in ("n", "nagad", "নগদ"):
        return "N"
    # SG, Cash, Mobile, ?, Agent, etc. → NULL (unknown)
    return ""


def parse_date_feb(raw: str) -> str:
    """Parse date like '01-02-2026' (DD-MM-YYYY) to YYYY-MM-DD."""
    if not raw:
        return ""
    raw = raw.strip()
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def parse_date_mar(raw: str) -> str:
    """Parse date like '01/04/2026' (DD/MM/YYYY) to YYYY-MM-DD."""
    if not raw:
        return ""
    raw = raw.strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def generate_sql():
    """Generate SQL statements for importing all data."""
    sql_lines = []
    sql_lines.append("-- Phase 4 CSV Import Script")
    sql_lines.append("-- Generated: " + datetime.now().isoformat())
    sql_lines.append("BEGIN;")
    sql_lines.append("")

    # ============================================================
    # STEP 1: Extract unique employees from both CSV files
    # ============================================================
    employees = {}  # mobile → name

    # Feb CSV
    with open("/tmp/cashPayment_FebruaryDB_2026.csv", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            eid = normalize_mobile(row.get("employee_id", ""))
            name = (row.get("name") or "").strip()
            if eid and name and eid not in employees:
                employees[eid] = name

    # Mar-Apr CSV
    with open("/tmp/cashPayment_MarchApril.csv", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            eid = normalize_mobile(row.get("employee_id", ""))
            name = (row.get("name") or "").strip()
            if eid and name and eid not in employees:
                employees[eid] = name

    sql_lines.append("-- STEP 1: Upsert employees (unique from payment CSVs)")
    sql_lines.append(f"-- Total unique employees: {len(employees)}")
    for mobile, name in sorted(employees.items()):
        safe_name = name.replace("'", "''")
        sql_lines.append(
            f"INSERT INTO ops_employees (employee_id, name, mobile, role) "
            f"VALUES ('{mobile}', '{safe_name}', '{mobile}', 'escort') "
            f"ON CONFLICT (employee_id) DO UPDATE SET name = EXCLUDED.name;"
        )
    sql_lines.append("")

    # ============================================================
    # STEP 2: Import February payments
    # ============================================================
    sql_lines.append("-- STEP 2: Import February 2026 payments")
    feb_count = 0
    with open("/tmp/cashPayment_FebruaryDB_2026.csv", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not any(v.strip() for v in row.values() if v):
                continue
            eid = normalize_mobile(row.get("employee_id", ""))
            if not eid:
                continue
            name = (row.get("name") or "").strip().replace("'", "''")
            amount = parse_amount(row.get("amount", ""))
            if amount <= 0:
                continue
            method = map_method(row.get("method", ""))
            category = (row.get("category") or "").strip().lower()
            if category not in ("food", "transport", "salary", "advance"):
                category = "general"
            payment_date = parse_date_feb(row.get("payment_date", ""))
            paid_by = normalize_mobile(row.get("paid_by", ""))
            payment_number = normalize_mobile(row.get("payment_number", ""))
            remarks = (row.get("remarks") or "").strip().replace("'", "''")

            method_sql = f"'{method}'" if method else "NULL"
            date_sql = f"'{payment_date}'" if payment_date else "CURRENT_DATE"
            paid_by_sql = f"'{paid_by}'" if paid_by else "NULL"
            pn_sql = f"'{payment_number}'" if payment_number else "NULL"
            remarks_sql = f"'{remarks}'" if remarks else "NULL"

            sql_lines.append(
                f"INSERT INTO ops_payments (employee_id, name, amount, method, status, category, payment_date, paid_by, payment_number, remarks) "
                f"VALUES ('{eid}', '{name}', {amount}, {method_sql}, 'completed', '{category}', {date_sql}, {paid_by_sql}, {pn_sql}, {remarks_sql});"
            )
            feb_count += 1
    sql_lines.append(f"-- February rows inserted: {feb_count}")
    sql_lines.append("")

    # ============================================================
    # STEP 3: Import March-April payments
    # ============================================================
    sql_lines.append("-- STEP 3: Import March-April 2026 payments")
    mar_count = 0
    with open("/tmp/cashPayment_MarchApril.csv", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not any(v.strip() for v in row.values() if v):
                continue
            eid = normalize_mobile(row.get("employee_id", ""))
            if not eid:
                continue
            name = (row.get("name") or "").strip().replace("'", "''")
            amount = parse_amount(row.get("amount", ""))
            if amount <= 0:
                continue
            method = map_method(row.get("method", ""))
            category = (row.get("category") or "").strip().lower()
            if category not in ("food", "transport", "salary", "advance"):
                category = "general"
            payment_date = parse_date_mar(row.get("payment_date", ""))
            paid_by_raw = (row.get("paid_by") or "").strip().replace("'", "''")
            payment_number = normalize_mobile(row.get("payment_number", ""))
            remarks = (row.get("remarks") or "").strip().replace("'", "''")

            method_sql = f"'{method}'" if method else "NULL"
            date_sql = f"'{payment_date}'" if payment_date else "CURRENT_DATE"
            # paid_by is a name like "Mamun Vai" in this file, not a mobile
            paid_by_sql = f"'{paid_by_raw}'" if paid_by_raw else "NULL"
            pn_sql = f"'{payment_number}'" if payment_number else "NULL"
            remarks_sql = f"'{remarks}'" if remarks else "NULL"

            sql_lines.append(
                f"INSERT INTO ops_payments (employee_id, name, amount, method, status, category, payment_date, paid_by, payment_number, remarks) "
                f"VALUES ('{eid}', '{name}', {amount}, {method_sql}, 'completed', '{category}', {date_sql}, {paid_by_sql}, {pn_sql}, {remarks_sql});"
            )
            mar_count += 1
    sql_lines.append(f"-- March-April rows inserted: {mar_count}")
    sql_lines.append("")

    # ============================================================
    # STEP 4: Import contacts → fazle_social_contacts
    # ============================================================
    sql_lines.append("-- STEP 4: Import contacts")
    contact_count = 0
    with open("/tmp/contacts.csv", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not any(v.strip() for v in row.values() if v):
                continue
            first = (row.get("First Name") or "").strip()
            middle = (row.get("Middle Name") or "").strip()
            last = (row.get("Last Name") or "").strip()
            name = " ".join(part for part in [first, middle, last] if part).strip()
            if not name:
                continue

            phone = (row.get("Phone 1 - Value") or "").strip()
            mobile = normalize_mobile(phone)
            if not mobile:
                continue

            org = (row.get("Organization Name") or "").strip().replace("'", "''")
            safe_name = name.replace("'", "''")
            metadata = {}
            if org:
                metadata["company"] = org

            meta_json = json.dumps(metadata).replace("'", "''")

            sql_lines.append(
                f"INSERT INTO fazle_social_contacts (name, platform, identifier, metadata) "
                f"VALUES ('{safe_name}', 'whatsapp', '88{mobile[1:]}', '{meta_json}') "
                f"ON CONFLICT (platform, identifier) DO UPDATE SET name = EXCLUDED.name, "
                f"metadata = fazle_social_contacts.metadata || EXCLUDED.metadata;"
            )
            contact_count += 1

    sql_lines.append(f"-- Contacts inserted/updated: {contact_count}")
    sql_lines.append("")

    sql_lines.append("COMMIT;")
    sql_lines.append("")
    sql_lines.append(f"-- SUMMARY:")
    sql_lines.append(f"-- Employees upserted: {len(employees)}")
    sql_lines.append(f"-- Feb payments inserted: {feb_count}")
    sql_lines.append(f"-- Mar-Apr payments inserted: {mar_count}")
    sql_lines.append(f"-- Total new payments: {feb_count + mar_count}")
    sql_lines.append(f"-- Contacts imported: {contact_count}")

    return "\n".join(sql_lines)


if __name__ == "__main__":
    sql = generate_sql()
    with open("/tmp/import_phase4.sql", "w", encoding="utf-8") as f:
        f.write(sql)
    print(f"SQL written to /tmp/import_phase4.sql")
    # Print summary
    for line in sql.split("\n"):
        if line.startswith("-- "):
            print(line)
