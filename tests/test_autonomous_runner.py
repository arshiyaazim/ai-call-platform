# ============================================================
# Tests for Fazle Phase-5 Autonomous Task Runner
#
# Run:  pytest tests/test_autonomous_runner.py -v
# ============================================================
import pytest
from conftest import autonomous_runner as _m


# ── Model validation ───────────────────────────────────────

def test_task_create_request():
    """CreateTaskRequest should accept name, type, description, interval."""
    req = _m.CreateTaskRequest(name="Daily Digest", task_type=_m.TaskType.digest, description="Summarize daily events")
    assert req.name == "Daily Digest"
    assert req.task_type == _m.TaskType.digest
    assert req.description == "Summarize daily events"
    assert req.config == {}


def test_task_create_with_config():
    """CreateTaskRequest should accept optional config dict."""
    req = _m.CreateTaskRequest(
        name="Monitor API",
        task_type=_m.TaskType.monitor,
        description="Monitor API endpoint uptime",
        config={"url": "https://example.com", "keyword": "status"},
        interval_minutes=5,
    )
    assert req.config == {"url": "https://example.com", "keyword": "status"}
    assert req.interval_minutes == 5


# ── Valid task types ───────────────────────────────────────

def test_valid_task_types():
    """TaskType enum should contain all expected types."""
    assert _m.TaskType.research.value == "research"
    assert _m.TaskType.monitor.value == "monitor"
    assert _m.TaskType.digest.value == "digest"
    assert _m.TaskType.learning.value == "learning"
    assert _m.TaskType.custom.value == "custom"
    assert _m.TaskType.reminder.value == "reminder"


# ── Task store ──────────────────────────────────────────────

def test_task_store_is_dict():
    """In-memory task store should be a dict."""
    assert isinstance(_m._tasks, dict)


# ── Health & task endpoints ─────────────────────────────────

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
        assert data["service"] == "autonomous-runner"


@pytest.mark.anyio
async def test_create_and_list_tasks():
    """POST /tasks/autonomous then GET /tasks/autonomous should return task."""
    from httpx import AsyncClient, ASGITransport
    _m._tasks.clear()
    for handle in _m._background_handles.values():
        handle.cancel()
    _m._background_handles.clear()
    transport = ASGITransport(app=_m.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post("/tasks/autonomous", json={
            "name": "Test Research",
            "task_type": "research",
            "description": "Research AI trends",
        })
        assert create_resp.status_code == 200
        task_data = create_resp.json()
        assert task_data["task"]["name"] == "Test Research"
        assert task_data["task"]["status"] == "active"

        list_resp = await client.get("/tasks/autonomous")
        assert list_resp.status_code == 200
        tasks = list_resp.json()["tasks"]
        assert len(tasks) == 1

    # Cleanup
    for handle in _m._background_handles.values():
        handle.cancel()
    _m._background_handles.clear()


@pytest.mark.anyio
async def test_list_history_empty():
    """GET /tasks/autonomous/history should return empty list initially."""
    from httpx import AsyncClient, ASGITransport
    _m._run_history.clear()
    transport = ASGITransport(app=_m.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/tasks/autonomous/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["history"] == []
