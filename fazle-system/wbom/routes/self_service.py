# ============================================================
# WBOM — Employee Self-Service Routes
# Handles employee incoming messages and request management
# ============================================================
from typing import Optional

from fastapi import APIRouter, Query
from models import EmployeeRequestCreate
from services.self_service import (
    process_employee_message,
    get_pending_requests,
    respond_to_request,
)

router = APIRouter(prefix="/self-service", tags=["Employee Self-Service"])


@router.post("/message")
async def handle_employee_message(sender_number: str, message_body: str):
    """Process an incoming message from an employee."""
    return process_employee_message(sender_number, message_body)


@router.get("/requests")
async def list_pending_requests(limit: int = Query(50, le=200)):
    """List all pending employee requests for admin review."""
    return get_pending_requests(limit=limit)


@router.post("/requests/{request_id}/respond")
async def respond_request(request_id: int, response_text: str, status: str = "Responded"):
    """Admin responds to an employee request."""
    return respond_to_request(request_id, response_text, status)
