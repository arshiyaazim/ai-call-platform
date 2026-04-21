# ============================================================
# WBOM — Dashboard Service Tests  (Sprint-2 D0-01)
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


# ── Helpers ───────────────────────────────────────────────────

_REF = date(2026, 5, 15)  # deterministic reference date

def _make_execute_query(seq):
    """Return an execute_query mock that pops responses from *seq* in order."""
    responses = list(seq)
    idx = [0]

    def _mock(sql, params=()):
        if idx[0] < len(responses):
            result = responses[idx[0]]
            idx[0] += 1
            return result
        return []

    return _mock


# ── D0-01 Tests ───────────────────────────────────────────────

def test_dashboard_summary_basic(monkeypatch):
    """Returns expected KPI shape with all numeric fields."""
    responses = [
        [{"cnt": 20}],          # active_employees
        [{"cnt": 3}],           # programs_today
        [{"cnt": 1}],           # absent_today
        [                       # payroll_status
            {"status": "draft", "cnt": 5},
            {"status": "paid",  "cnt": 2},
        ],
        [{"cnt": 1}],           # overdue_payroll
        [{"cnt": 0}],           # unpaid_advance
        [{"total_advances": Decimal("500"), "total_deductions": Decimal("200"),
          "total_salary_out": Decimal("30000"), "total_other": Decimal("100")}],
    ]
    monkeypatch.setattr(dash_svc, "execute_query", _make_execute_query(responses))

    result = dash_svc.get_dashboard_summary(ref_date=_REF)

    assert result["active_employees"] == 20
    assert result["programs_today"]   == 3
    assert result["absent_today"]     == 1
    assert result["payroll_status"]["draft"] == 5
    assert result["payroll_status"]["paid"]  == 2
    assert result["alerts"]["overdue_payroll"] == 1
    assert result["alerts"]["unpaid_advance"]  == 0
    assert result["cash_flow"]["total_advances"] == 500.0
    assert result["ref_date"] == "2026-05-15"


def test_dashboard_summary_empty_db(monkeypatch):
    """All queries return empty — all KPIs should be zero, not an error."""
    responses = [[], [], [], [], [], [], []]
    monkeypatch.setattr(dash_svc, "execute_query", _make_execute_query(responses))

    result = dash_svc.get_dashboard_summary(ref_date=_REF)

    assert result["active_employees"] == 0
    assert result["programs_today"]   == 0
    assert result["absent_today"]     == 0
    for v in result["payroll_status"].values():
        assert v == 0
    assert result["alerts"]["overdue_payroll"] == 0
    assert result["cash_flow"]["total_salary_out"] == 0.0


def test_dashboard_summary_defaults_to_today(monkeypatch):
    """When ref_date is None the function uses today without raising."""
    responses = [
        [{"cnt": 5}], [{"cnt": 0}], [{"cnt": 0}], [], [{"cnt": 0}], [{"cnt": 0}],
        [{"total_advances": 0, "total_deductions": 0,
          "total_salary_out": 0, "total_other": 0}],
    ]
    monkeypatch.setattr(dash_svc, "execute_query", _make_execute_query(responses))

    result = dash_svc.get_dashboard_summary()  # no ref_date

    assert result["ref_date"] == str(date.today())
    assert result["active_employees"] == 5


def test_dashboard_summary_period_fields(monkeypatch):
    """Period year/month must match ref_date."""
    responses = [
        [{"cnt": 0}],  # active_employees
        [{"cnt": 0}],  # programs_today
        [{"cnt": 0}],  # absent_today
        [],            # payroll_status (empty — no rows this period)
        [{"cnt": 0}],  # overdue_payroll
        [{"cnt": 0}],  # unpaid_advance
        [{"total_advances": 0, "total_deductions": 0,
          "total_salary_out": 0, "total_other": 0}],
    ]
    monkeypatch.setattr(dash_svc, "execute_query", _make_execute_query(responses))

    result = dash_svc.get_dashboard_summary(ref_date=date(2025, 12, 31))

    assert result["period"]["year"]  == 2025
    assert result["period"]["month"] == 12


def test_dashboard_all_payroll_statuses_present(monkeypatch):
    """All five status keys always present even if DB returns a subset."""
    responses = [
        [{"cnt": 10}], [{"cnt": 0}], [{"cnt": 0}],
        [{"status": "approved", "cnt": 3}],   # only one status row returned
        [{"cnt": 0}], [{"cnt": 0}],
        [{"total_advances": 0, "total_deductions": 0,
          "total_salary_out": 0, "total_other": 0}],
    ]
    monkeypatch.setattr(dash_svc, "execute_query", _make_execute_query(responses))

    result = dash_svc.get_dashboard_summary(ref_date=_REF)

    ps = result["payroll_status"]
    for key in ("draft", "reviewed", "approved", "locked", "paid"):
        assert key in ps, f"Missing key: {key}"
    assert ps["approved"] == 3
    assert ps["draft"] == 0


def test_dashboard_cash_flow_types(monkeypatch):
    """Cash flow values are floats, not Decimal."""
    responses = [
        [{"cnt": 1}], [{"cnt": 0}], [{"cnt": 0}], [], [{"cnt": 0}], [{"cnt": 0}],
        [{"total_advances": Decimal("1234.56"), "total_deductions": Decimal("0"),
          "total_salary_out": Decimal("99999.99"), "total_other": Decimal("50")}],
    ]
    monkeypatch.setattr(dash_svc, "execute_query", _make_execute_query(responses))

    result = dash_svc.get_dashboard_summary(ref_date=_REF)

    assert isinstance(result["cash_flow"]["total_advances"],   float)
    assert isinstance(result["cash_flow"]["total_salary_out"], float)
    assert abs(result["cash_flow"]["total_advances"] - 1234.56) < 0.001
