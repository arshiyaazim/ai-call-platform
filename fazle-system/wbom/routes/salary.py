# ============================================================
# WBOM — Salary Routes
# Auto-generation and management of salary records
# ============================================================
from fastapi import APIRouter, HTTPException, Query

from models import SalaryGenerateRequest, SalaryResponse
from services.salary_generator import generate_salary, get_salary_summary, mark_salary_paid

router = APIRouter(prefix="/salary", tags=["salary"])


@router.post("/generate", response_model=SalaryResponse)
def generate(req: SalaryGenerateRequest):
    record = generate_salary(
        employee_id=req.employee_id,
        month=req.month,
        year=req.year,
        basic_salary=req.basic_salary,
        program_allowance=req.program_allowance,
        other_allowance=req.other_allowance,
        remarks=req.remarks,
    )
    return record


@router.get("/summary")
def summary(month: int = Query(..., ge=1, le=12), year: int = Query(..., ge=2020, le=2099)):
    rows = get_salary_summary(month, year)
    total = sum(r.get("net_salary", 0) for r in rows)
    return {"month": month, "year": year, "records": rows, "total_payable": total}


@router.post("/mark-paid/{salary_id}")
def paid(salary_id: int):
    ok = mark_salary_paid(salary_id)
    if not ok:
        raise HTTPException(404, "Salary record not found")
    return {"paid": True}
