# ============================================================
# WBOM — Cash Transaction Routes
# CRUD + daily summary for cash flow tracking
# ============================================================
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import date

from database import insert_row, get_row, delete_row, list_rows, execute_query
from models import TransactionCreate, TransactionResponse

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("", response_model=TransactionResponse, status_code=201)
def create_transaction(data: TransactionCreate):
    row = insert_row("wbom_cash_transactions", data.model_dump(exclude_none=True))
    return row


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(transaction_id: int):
    row = get_row("wbom_cash_transactions", "transaction_id", transaction_id)
    if not row:
        raise HTTPException(404, "Transaction not found")
    return row


@router.delete("/{transaction_id}")
def remove_transaction(transaction_id: int):
    if not delete_row("wbom_cash_transactions", "transaction_id", transaction_id):
        raise HTTPException(404, "Transaction not found")
    return {"deleted": True}


@router.get("", response_model=list[TransactionResponse])
def list_transactions(
    transaction_type: Optional[str] = None,
    payment_method: Optional[str] = None,
    transaction_date: Optional[date] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    filters = {}
    if transaction_type:
        filters["transaction_type"] = transaction_type
    if payment_method:
        filters["payment_method"] = payment_method
    if transaction_date:
        filters["transaction_date"] = str(transaction_date)
    return list_rows(
        "wbom_cash_transactions", filters, "transaction_date DESC, transaction_time DESC", limit, offset
    )


@router.get("/daily-summary/{day}")
def daily_summary(day: date):
    sql = """
        SELECT
            transaction_type,
            payment_method,
            COUNT(*) AS count,
            COALESCE(SUM(amount), 0) AS total
        FROM wbom_cash_transactions
        WHERE transaction_date = %s
        GROUP BY transaction_type, payment_method
        ORDER BY transaction_type, payment_method
    """
    rows = execute_query(sql, (str(day),))
    income = sum(r["total"] for r in rows if r["transaction_type"] == "Income")
    expense = sum(r["total"] for r in rows if r["transaction_type"] == "Expense")
    return {"date": str(day), "breakdown": rows, "total_income": income, "total_expense": expense, "net": income - expense}


@router.get("/by-employee/{employee_id}", response_model=list[TransactionResponse])
def transactions_by_employee(employee_id: int, limit: int = Query(50, le=200)):
    return list_rows(
        "wbom_cash_transactions", {"employee_id": employee_id}, "transaction_date DESC", limit, 0
    )
