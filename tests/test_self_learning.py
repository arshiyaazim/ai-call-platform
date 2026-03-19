# ============================================================
# Tests for Fazle Phase-5 Self-Learning Engine
#
# Run:  pytest tests/test_self_learning.py -v
# ============================================================
import pytest
from conftest import self_learning as _m


# ── Model validation ───────────────────────────────────────

def test_analyze_request():
    """AnalyzeRequest should accept conversation text."""
    req = _m.AnalyzeRequest(text="User asked about weather")
    assert req.text == "User asked about weather"
    assert req.focus_area is None


def test_analyze_request_with_focus():
    """AnalyzeRequest should accept optional focus_area."""
    req = _m.AnalyzeRequest(text="Hello", focus_area="routing")
    assert req.focus_area == "routing"


def test_improve_request():
    """ImproveRequest should accept optional area."""
    req = _m.ImproveRequest(area="routing")
    assert req.area == "routing"
    assert req.auto_apply is False


# ── Insight types ──────────────────────────────────────────

def test_insight_types():
    """InsightType enum should contain all expected types."""
    assert _m.InsightType.pattern.value == "pattern"
    assert _m.InsightType.preference.value == "preference"
    assert _m.InsightType.improvement.value == "improvement"
    assert _m.InsightType.routing_optimization.value == "routing_optimization"
    assert _m.InsightType.knowledge_gap.value == "knowledge_gap"
    assert _m.InsightType.behavioral.value == "behavioral"


# ── Insight store ──────────────────────────────────────────

def test_insight_store_is_dict():
    """In-memory insight store should be a dict."""
    assert isinstance(_m._insights, dict)


# ── Health & insight endpoints ──────────────────────────────

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
        assert data["service"] == "self-learning"


@pytest.mark.anyio
async def test_list_insights_empty():
    """GET /learning/insights should return empty list when cleared."""
    from httpx import AsyncClient, ASGITransport
    _m._insights.clear()
    transport = ASGITransport(app=_m.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/learning/insights")
        assert resp.status_code == 200
        data = resp.json()
        assert data["insights"] == []


@pytest.mark.anyio
async def test_stats_endpoint():
    """GET /learning/stats should return counters."""
    from httpx import AsyncClient, ASGITransport
    transport = ASGITransport(app=_m.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/learning/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_insights" in data
