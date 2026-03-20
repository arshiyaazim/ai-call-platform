# ============================================================
# Fazle API — Watchdog / AI Control Panel Routes
# System status, container management, AI pause/resume
# ============================================================
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import httpx
import logging
from typing import Optional
from datetime import datetime

from auth import require_admin, get_current_user

logger = logging.getLogger("fazle-api")

router = APIRouter(prefix="/fazle/system", tags=["watchdog"])


# ── Models ──────────────────────────────────────────────────
class ContainerRestartRequest(BaseModel):
    container_name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_\-]+$")


# ── Service URLs (reuse from settings via import) ──────────
def _get_settings():
    from main import settings
    return settings


@router.get("/status")
async def system_status(user: dict = Depends(require_admin)):
    """Get comprehensive system status: containers, AI activity, safety."""
    settings = _get_settings()
    result = {
        "timestamp": datetime.utcnow().isoformat(),
        "containers": {"total": 0, "healthy": 0, "unhealthy": 0, "details": []},
        "resources": {"cpu_percent": 0, "memory_percent": 0},
        "ai_activity": {
            "running_agents": 0,
            "running_workflows": 0,
            "queued_tasks": 0,
            "active_tool_executions": 0,
        },
        "safety": {"blocked_actions": 0, "high_risk_actions": 0},
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Container health from Prometheus
        try:
            r = await client.get(
                "http://prometheus:9090/api/v1/query",
                params={"query": 'up{job=~"fazle-.*|postgres|redis|qdrant|nginx"}'},
            )
            if r.status_code == 200:
                data = r.json().get("data", {}).get("result", [])
                healthy = sum(1 for d in data if d["value"][1] == "1")
                result["containers"]["total"] = len(data)
                result["containers"]["healthy"] = healthy
                result["containers"]["unhealthy"] = len(data) - healthy
                result["containers"]["details"] = [
                    {
                        "name": d["metric"].get("job", "unknown"),
                        "instance": d["metric"].get("instance", ""),
                        "up": d["value"][1] == "1",
                    }
                    for d in data
                ]
        except Exception as e:
            logger.warning(f"Failed to fetch container status: {e}")

        # CPU usage
        try:
            r = await client.get(
                "http://prometheus:9090/api/v1/query",
                params={"query": 'avg(rate(container_cpu_usage_seconds_total{name=~"fazle-.*"}[5m])) * 100'},
            )
            if r.status_code == 200:
                data = r.json().get("data", {}).get("result", [])
                if data:
                    result["resources"]["cpu_percent"] = round(float(data[0]["value"][1]), 2)
        except Exception:
            pass

        # Memory usage
        try:
            r = await client.get(
                "http://prometheus:9090/api/v1/query",
                params={"query": 'avg(container_memory_usage_bytes{name=~"fazle-.*"} / container_spec_memory_limit_bytes) * 100'},
            )
            if r.status_code == 200:
                data = r.json().get("data", {}).get("result", [])
                if data:
                    result["resources"]["memory_percent"] = round(float(data[0]["value"][1]), 2)
        except Exception:
            pass

        # AI activity — workflows
        try:
            r = await client.get(f"{settings.workflow_engine_url}/workflows", params={"status": "running", "limit": 100})
            if r.status_code == 200:
                workflows = r.json().get("workflows", [])
                result["ai_activity"]["running_workflows"] = len(workflows)
        except Exception:
            pass

        # AI activity — autonomous tasks
        try:
            r = await client.get(f"{settings.autonomous_runner_url}/tasks/autonomous", params={"status": "running", "limit": 100})
            if r.status_code == 200:
                tasks = r.json().get("tasks", [])
                result["ai_activity"]["queued_tasks"] = len(tasks)
        except Exception:
            pass

        # Guardrail stats
        try:
            r = await client.get(f"{settings.guardrail_url}/guardrail/stats")
            if r.status_code == 200:
                stats = r.json()
                result["safety"]["blocked_actions"] = stats.get("total_blocked", 0)
                result["safety"]["high_risk_actions"] = stats.get("high_risk_count", 0)
        except Exception:
            pass

    return result


@router.post("/container/restart")
async def container_restart(request: ContainerRestartRequest, admin: dict = Depends(require_admin)):
    """Restart a specific container. Admin only.
    Note: This sends a restart signal via the Docker API socket if mounted,
    otherwise returns instructions."""
    # Allowlist of containers that can be restarted
    allowed = {
        "fazle-api", "fazle-brain", "fazle-memory", "fazle-task-engine",
        "fazle-tool-engine", "fazle-autonomy-engine", "fazle-knowledge-graph",
        "fazle-autonomous-runner", "fazle-self-learning", "fazle-guardrail-engine",
        "fazle-workflow-engine", "fazle-social-engine",
    }
    if request.container_name not in allowed:
        raise HTTPException(status_code=400, detail=f"Container not in allowlist: {', '.join(sorted(allowed))}")

    from audit import log_action
    log_action(admin, "container_restart", target_type="container", detail=request.container_name)

    return {
        "status": "restart_requested",
        "container": request.container_name,
        "note": "Use docker compose restart on VPS to complete restart",
        "command": f"docker compose restart {request.container_name}",
    }


@router.post("/ai/pause")
async def ai_pause(admin: dict = Depends(require_admin)):
    """Pause all AI autonomous operations."""
    settings = _get_settings()
    results = {}
    async with httpx.AsyncClient(timeout=15.0) as client:
        # Pause autonomous runner
        try:
            r = await client.post(f"{settings.autonomous_runner_url}/tasks/autonomous/pause-all")
            results["autonomous_runner"] = "paused" if r.status_code == 200 else "failed"
        except Exception:
            results["autonomous_runner"] = "unreachable"

        # Pause workflows
        try:
            r = await client.post(f"{settings.workflow_engine_url}/workflows/pause-all")
            results["workflow_engine"] = "paused" if r.status_code == 200 else "failed"
        except Exception:
            results["workflow_engine"] = "unreachable"

    from audit import log_action
    log_action(admin, "ai_pause", target_type="system", detail=str(results))
    return {"status": "pause_requested", "results": results}


@router.post("/ai/resume")
async def ai_resume(admin: dict = Depends(require_admin)):
    """Resume all AI autonomous operations."""
    settings = _get_settings()
    results = {}
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.post(f"{settings.autonomous_runner_url}/tasks/autonomous/resume-all")
            results["autonomous_runner"] = "resumed" if r.status_code == 200 else "failed"
        except Exception:
            results["autonomous_runner"] = "unreachable"

        try:
            r = await client.post(f"{settings.workflow_engine_url}/workflows/resume-all")
            results["workflow_engine"] = "resumed" if r.status_code == 200 else "failed"
        except Exception:
            results["workflow_engine"] = "unreachable"

    from audit import log_action
    log_action(admin, "ai_resume", target_type="system", detail=str(results))
    return {"status": "resume_requested", "results": results}
