# ============================================================
# WBOM — Reports Sprint-2 Tests  (D0-02 + D0-03)
# All DB calls are monkeypatched — no real DB required.
# ============================================================
import os
import sys
import types
from datetime import date
from decimal import Decimal

# ── Bootstrap ────────────────────────────────────────────────
WBOM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WBOM_DIR not in sys.path:
    sys.path.insert(0, WBOM_DIR)

# ── psycopg2 stub ─────────────────────────────────────────────
if "psycopg2" not in sys.modules:
    psycopg2_stub = types.ModuleType("psycopg2")
    extras_stub   = types.ModuleType("psycopg2.extras")
    pool_stub      = types.ModuleType("psycopg2.pool")

    class _ThreadedConnectionPool:
        def __init__(self, *a, **kw): pass
        def getconn(self): return _FakeConn()
        def putconn(self, c): pass

    class _RealDictCursor: pass

    class _FakeConn:
        def cursor(self, *a, **kw): return _FakeCursor()
        def commit(self): pass
        def rollback(self): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass

    class _FakeCursor:
        def execute(self, *a, **kw): pass
        def fetchone(self): return None
        def fetchall(self): return []
        def __enter__(self): return self
        def __exit__(self, *a): pass

    pool_stub.ThreadedConnectionPool = _ThreadedConnectionPool
    extras_stub.RealDictCursor = _RealDictCursor
    psycopg2_stub.extras = extras_stub
    psycopg2_stub.pool   = pool_stub
    sys.modules["psycopg2"]        = psycopg2_stub
    sys.modules["psycopg2.extras"] = extras_stub
    sys.modules["psycopg2.pool"]   = pool_stub

# ── prometheus stub ───────────────────────────────────────────
if "prometheus_fastapi_instrumentator" not in sys.modules:
    pfi = types.ModuleType("prometheus_fastapi_instrumentator")
    class _Inst:
        def instrument(self, *a, **kw): return self
        def expose(self, *a, **kw): return self
    pfi.Instrumentator = _Inst
    sys.modules["prometheus_fastapi_instrumentator"] = pfi

import services.dashboard as dash_svc

_REF = date(2026, 5, 15)


def _make_execute_query(seq):
    responses = list(seq)
    idx = [0]

    def _mock(sql, params=()):
        if idx[0] < len(responses):
            result = responses[idx[0]]
            idx[0] += 1
            return result
        return []

    return _mock


# ── D0-02: Daily Activity Tests ───────────────────────────────

def test_daily_activity_returns_date(monkeypatch):
    """Result date matches the input date."""
    monkeypatch.setattr(dash_svc, "execute_query", _make_execute_query([[], [], []]))
    result = dash_svc.get_daily_activity(_REF)
    assert result["date"] == "2026-05-15"


def test_daily_activity_programs_populated(monkeypatch):
    """Programs list is returned correctly."""
    programs = [
        {"program_id": 1, "mother_vessel": "MV Alpha", "lighter_vessel": "LV Beta",
         "program_date": _REF, "shift": "D", "status": "Running",
         "escort_name": "Alice"},
    ]
    monkeypatch.setattr(dash_svc, "execute_query", _make_execute_query([programs, [], []]))
    result = dash_svc.get_daily_activity(_REF)
    assert len(result["programs"]) == 1
    assert result["programs"][0]["mother_vessel"] == "MV Alpha"


def test_daily_activity_attendance_counts(monkeypatch):
    """Present/absent tallies are computed correctly."""
    attendance = [
        {"attendance_id": 1, "employee_id": 1, "employee_name": "Alice",
         "status": "Present", "check_in_time": None, "check_out_time": None, "location": None},
        {"attendance_id": 2, "employee_id": 2, "employee_name": "Bob",
         "status": "Absent",  "check_in_time": None, "check_out_time": None, "location": None},
        {"attendance_id": 3, "employee_id": 3, "employee_name": "Carol",
         "status": "Present", "check_in_time": None, "check_out_time": None, "location": None},
    ]
    monkeypatch.setattr(dash_svc, "execute_query", _make_execute_query([[], attendance, []]))
    result = dash_svc.get_daily_activity(_REF)
    assert result["attendance"]["present"] == 2
    assert result["attendance"]["absent"]  == 1
    assert len(result["attendance"]["records"]) == 3


def test_daily_activity_transactions_list(monkeypatch):
    """Transactions list is returned."""
    txns = [
        {"transaction_id": 10, "employee_id": 1, "employee_name": "Alice",
         "transaction_type": "Advance", "amount": Decimal("500"),
         "payment_method": "Cash", "status": "Completed", "remarks": None},
    ]
    monkeypatch.setattr(dash_svc, "execute_query", _make_execute_query([[], [], txns]))
    result = dash_svc.get_daily_activity(_REF)
    assert len(result["transactions"]) == 1
    assert result["transactions"][0]["transaction_type"] == "Advance"


def test_daily_activity_empty_day(monkeypatch):
    """Empty day returns zeroed structure without error."""
    monkeypatch.setattr(dash_svc, "execute_query", _make_execute_query([[], [], []]))
    result = dash_svc.get_daily_activity(_REF)
    assert result["programs"] == []
    assert result["attendance"]["present"] == 0
    assert result["attendance"]["absent"]  == 0
    assert result["transactions"] == []


# ── D0-03: Monthly Payroll Report Tests ───────────────────────

def test_monthly_payroll_period_matches(monkeypatch):
    """Period year/month matches the input."""
    monkeypatch.setattr(dash_svc, "execute_query", _make_execute_query([[], []]))
    result = dash_svc.get_monthly_payroll_report(2026, 5)
    assert result["period"]["year"]  == 2026
    assert result["period"]["month"] == 5


def test_monthly_payroll_totals(monkeypatch):
    """total_runs, paid_count, and total_net_salary are computed correctly."""
    runs = [
        {"run_id": 1, "employee_id": 1, "employee_name": "Alice",
         "designation": "Escort", "status": "paid",
         "basic_salary": Decimal("10000"), "total_programs": 5,
         "program_allowance": Decimal("2500"), "other_allowance": Decimal("0"),
         "total_advances": Decimal("500"), "total_deductions": Decimal("0"),
         "gross_salary": Decimal("12500"), "net_salary": Decimal("12000"),
         "payout_target_date": None, "payment_method": "Cash", "paid_at": None,
         "per_program_rate": Decimal("500")},
        {"run_id": 2, "employee_id": 2, "employee_name": "Bob",
         "designation": "Escort", "status": "draft",
         "basic_salary": Decimal("8000"), "total_programs": 3,
         "program_allowance": Decimal("1500"), "other_allowance": Decimal("0"),
         "total_advances": Decimal("0"), "total_deductions": Decimal("0"),
         "gross_salary": Decimal("9500"), "net_salary": Decimal("9500"),
         "payout_target_date": None, "payment_method": None, "paid_at": None,
         "per_program_rate": Decimal("500")},
    ]
    cash = [{"total_advances": Decimal("500"), "total_deductions": Decimal("0"),
             "total_salary_out": Decimal("12000")}]
    monkeypatch.setattr(dash_svc, "execute_query", _make_execute_query([runs, cash]))

    result = dash_svc.get_monthly_payroll_report(2026, 5)

    assert result["total_runs"]  == 2
    assert result["paid_count"]  == 1
    assert abs(result["total_net_salary"] - 21500.0) < 0.01
    assert len(result["payroll_runs"]) == 2


def test_monthly_payroll_empty_month(monkeypatch):
    """Empty month: zero counts, empty list."""
    monkeypatch.setattr(dash_svc, "execute_query", _make_execute_query([[], []]))
    result = dash_svc.get_monthly_payroll_report(2026, 1)
    assert result["total_runs"]       == 0
    assert result["paid_count"]       == 0
    assert result["total_net_salary"] == 0.0
    assert result["payroll_runs"]     == []


def test_monthly_payroll_cash_summary(monkeypatch):
    """Cash summary fields are floats matching query result."""
    cash = [{"total_advances": Decimal("2000"), "total_deductions": Decimal("300"),
             "total_salary_out": Decimal("50000")}]
    monkeypatch.setattr(dash_svc, "execute_query", _make_execute_query([[], cash]))

    result = dash_svc.get_monthly_payroll_report(2026, 5)

    cs = result["cash_summary"]
    assert cs["total_advances"]   == 2000.0
    assert cs["total_deductions"] == 300.0
    assert cs["total_salary_out"] == 50000.0
