# ============================================================
# Tests for Fazle Phase-5 Autonomy Engine
#
# Run:  pytest tests/test_autonomy_engine.py -v
# ============================================================
import pytest
from conftest import autonomy_engine as _m


# ── Model validation ───────────────────────────────────────

def test_plan_request_validation():
    """PlanRequest requires a goal string."""
    req = _m.PlanRequest(goal="Research AI trends")
    assert req.goal == "Research AI trends"
    assert req.context is None
    assert req.auto_execute is False


def test_plan_request_with_context():
    """PlanRequest should accept optional context and auto_execute."""
    req = _m.PlanRequest(goal="Summarize paper", context="Focus on NLP section", auto_execute=True)
    assert req.context == "Focus on NLP section"
    assert req.auto_execute is True


def test_execute_request_validation():
    """ExecuteRequest requires a plan_id string."""
    req = _m.ExecuteRequest(plan_id="test-plan-123")
    assert req.plan_id == "test-plan-123"


# ── Plan store ──────────────────────────────────────────────

def test_plan_store_initially_empty():
    """In-memory plan store should start as a dict."""
    assert isinstance(_m._plans, dict)


# ── Settings defaults ──────────────────────────────────────

def test_settings_defaults():
    """Settings should have default URLs for all dependencies."""
    s = _m.Settings()
    assert "8200" in s.brain_url
    assert "8300" in s.memory_url
    assert "9200" in s.tool_engine_url
    assert "9300" in s.knowledge_graph_url


# ── Health endpoint ─────────────────────────────────────────

@pytest.mark.anyio
async def test_health_endpoint():
    """Health endpoint should return status healthy."""
    from httpx import AsyncClient, ASGITransport
    transport = ASGITransport(app=_m.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["service"] == "autonomy-engine"


@pytest.mark.anyio
async def test_list_plans_empty():
    """GET /autonomy/plans should return empty list when cleared."""
    from httpx import AsyncClient, ASGITransport
    _m._plans.clear()
    transport = ASGITransport(app=_m.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/autonomy/plans")
        assert resp.status_code == 200
        data = resp.json()
        assert data["plans"] == []
