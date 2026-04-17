# ============================================================
# WBOM — Admin Command Routes
# Unified admin command processor + payment draft endpoints
# ============================================================
from datetime import date
from typing import Optional

from fastapi import APIRouter, Query
from models import (
    AdminCommandRequest,
    AdminCommandResponse,
    PaymentDraftRequest,
    PaymentDraftResponse,
)
from services.command_parser import parse_admin_command, execute_admin_command
from services.payment_draft import (
    generate_payment_draft,
    generate_bulk_salary_drafts,
    generate_daily_payment_summary,
)

router = APIRouter(prefix="/admin", tags=["Admin Commands"])


# ── Unified command endpoint ──────────────────────────────────

@router.post("/command", response_model=AdminCommandResponse)
async def process_admin_command(req: AdminCommandRequest):
    """Parse and execute an admin WhatsApp command."""
    parsed = parse_admin_command(req.message_body)
    result = execute_admin_command(parsed)
    return AdminCommandResponse(**result)


# ── Payment draft endpoints ───────────────────────────────────

@router.post("/payment-draft")
async def create_payment_draft(req: PaymentDraftRequest):
    """Generate a formatted payment draft message for the accountant."""
    return generate_payment_draft(
        employee_id=req.employee_id,
        amount=req.amount,
        payment_method=req.payment_method,
        transaction_type=req.transaction_type,
    )


@router.get("/salary-drafts")
async def get_salary_drafts(month: int = Query(...), year: int = Query(...)):
    """Generate bulk salary payment drafts for a month."""
    return generate_bulk_salary_drafts(month=month, year=year)


@router.get("/daily-summary")
async def get_daily_summary(target_date: Optional[date] = Query(None)):
    """Get daily payment summary."""
    return generate_daily_payment_summary(target_date=target_date)
