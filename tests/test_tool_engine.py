# ============================================================
# Tests for Fazle Phase-5 Tool Execution Engine
#
# Run:  pytest tests/test_tool_engine.py -v
# ============================================================
import pytest
from conftest import tool_engine as _m


# ── Model validation ───────────────────────────────────────

def test_tool_execute_request():
    """ExecuteToolRequest should accept tool name and parameters."""
    req = _m.ExecuteToolRequest(tool_name="web_search", parameters={"query": "AI news"})
    assert req.tool_name == "web_search"
    assert req.parameters == {"query": "AI news"}


def test_tool_execute_request_empty_params():
    """ExecuteToolRequest should default parameters to empty dict."""
    req = _m.ExecuteToolRequest(tool_name="memory_search")
    assert req.parameters == {}


# ── Built-in tool registry ─────────────────────────────────

def test_tool_registry_has_builtins():
    """Tool registry should contain all 6 built-in tools."""
    _m._register_defaults()
    expected = {"web_search", "http_request", "memory_search", "memory_store", "summarize", "code_sandbox"}
    assert expected.issubset(set(_m._tools.keys()))


def test_tool_has_required_fields():
    """Each tool should have name, description, category, and enabled."""
    _m._register_defaults()
    for name, tool in _m._tools.items():
        assert tool.name == name
        assert tool.description
        assert tool.category


# ── SSRF protection ────────────────────────────────────────

@pytest.mark.anyio
async def test_ssrf_blocked_private_ips():
    """http_request tool should block private/internal IP ranges via execution."""
    result = await _m._exec_http_request({"url": "http://127.0.0.1/secret"})
    assert "error" in result
    result2 = await _m._exec_http_request({"url": "http://localhost/admin"})
    assert "error" in result2
    result3 = await _m._exec_http_request({"url": "http://169.254.169.254/metadata"})
    assert "error" in result3


# ── Permissions model ──────────────────────────────────────

def test_default_permissions():
    """ToolPermissions should have sensible defaults."""
    perms = _m.ToolPermissions()
    assert perms.web_search is True
    assert perms.http_request is True
    assert perms.code_sandbox is False


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
        assert data["service"] == "tool-engine"


@pytest.mark.anyio
async def test_list_tools():
    """GET /tools/list should return all registered tools."""
    from httpx import AsyncClient, ASGITransport
    _m._register_defaults()
    transport = ASGITransport(app=_m.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/tools/list")
        assert resp.status_code == 200
        data = resp.json()
        assert "tools" in data
        assert len(data["tools"]) >= 6
