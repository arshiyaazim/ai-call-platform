# ============================================================
# WBOM — Fuzzy Search Service
# Trigram + SequenceMatcher fuzzy name search across employees
# ============================================================
import logging
from difflib import SequenceMatcher
from typing import Optional

from database import execute_query

logger = logging.getLogger("wbom.fuzzy_search")


def fuzzy_search_employees(query: str, limit: int = 5) -> list[dict]:
    """Search employees by name or mobile with fuzzy matching.

    Uses PostgreSQL pg_trgm similarity for initial candidates,
    then re-ranks with Python SequenceMatcher for better accuracy.
    Returns top matches with similarity scores.
    """
    query = query.strip()
    if not query:
        return []

    # Try exact mobile match first
    if query.replace("-", "").replace(" ", "").isdigit():
        mobile = query.replace("-", "").replace(" ", "")
        if not mobile.startswith("0") and len(mobile) == 10:
            mobile = "0" + mobile
        rows = execute_query(
            "SELECT *, 1.0 as db_similarity FROM wbom_employees "
            "WHERE employee_mobile = %s OR employee_mobile = %s LIMIT 1",
            (mobile, mobile.lstrip("0")),
        )
        if rows:
            rows[0]["similarity"] = 1.0
            return rows

    # Trigram similarity search (requires pg_trgm extension)
    try:
        rows = execute_query(
            "SELECT *, similarity(employee_name, %s) as db_similarity "
            "FROM wbom_employees "
            "WHERE similarity(employee_name, %s) > 0.1 "
            "   OR employee_name ILIKE %s "
            "   OR employee_mobile ILIKE %s "
            "ORDER BY similarity(employee_name, %s) DESC "
            "LIMIT %s",
            (query, query, f"%{query}%", f"%{query}%", query, limit * 2),
        )
    except Exception:
        # Fallback if pg_trgm not available
        logger.warning("pg_trgm not available, falling back to ILIKE search")
        rows = execute_query(
            "SELECT *, 0.5 as db_similarity FROM wbom_employees "
            "WHERE employee_name ILIKE %s OR employee_mobile ILIKE %s "
            "ORDER BY employee_name LIMIT %s",
            (f"%{query}%", f"%{query}%", limit * 2),
        )

    if not rows:
        return []

    # Re-rank with SequenceMatcher for better accuracy
    query_lower = query.lower()
    for row in rows:
        name_lower = row["employee_name"].lower()
        seq_ratio = SequenceMatcher(None, query_lower, name_lower).ratio()
        # Combine DB trigram score with SequenceMatcher
        db_sim = float(row.get("db_similarity", 0))
        row["similarity"] = round((db_sim * 0.4 + seq_ratio * 0.6), 3)

    # Sort by combined similarity descending
    rows.sort(key=lambda r: r["similarity"], reverse=True)

    # Clean up internal fields
    for row in rows:
        row.pop("db_similarity", None)

    return rows[:limit]


def find_employee_fuzzy(name: str, mobile: Optional[str] = None) -> Optional[dict]:
    """Find best matching employee by name and/or mobile.

    Returns single best match or None if no good match found.
    """
    if mobile:
        mobile = mobile.replace("-", "").replace(" ", "").replace("+880", "0")
        if not mobile.startswith("0") and len(mobile) == 10:
            mobile = "0" + mobile
        rows = execute_query(
            "SELECT * FROM wbom_employees WHERE employee_mobile = %s LIMIT 1",
            (mobile,),
        )
        if rows:
            return rows[0]

    if name:
        results = fuzzy_search_employees(name, limit=1)
        if results and results[0]["similarity"] >= 0.5:
            return results[0]

    return None
