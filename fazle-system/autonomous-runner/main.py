# ============================================================
# Fazle Autonomous Task Runner — Background Task Execution
# Runs continuous research, monitoring, reminders, and
# scheduled autonomous operations in the background
# ============================================================
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from prometheus_fastapi_instrumentator import Instrumentator
import httpx
import json
import logging
import uuid
import asyncio
from typing import Optional, Any
from datetime import datetime
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fazle-autonomous-runner")


class Settings(BaseSettings):
    brain_url: str = "http://fazle-brain:8200"
    memory_url: str = "http://fazle-memory:8300"
    tools_url: str = "http://fazle-web-intelligence:8500"
    autonomy_url: str = "http://fazle-autonomy-engine:9100"
    tool_engine_url: str = "http://fazle-tool-engine:9200"
    knowledge_graph_url: str = "http://fazle-knowledge-graph:9300"
    llm_gateway_url: str = "http://fazle-llm-gateway:8800"
    redis_url: str = "redis://redis:6379/9"
    max_concurrent_tasks: int = 5
    default_interval_minutes: int = 60
    max_task_runtime_seconds: int = 300

    class Config:
        env_prefix = "AUTO_RUNNER_"


settings = Settings()

app = FastAPI(title="Fazle Autonomous Task Runner", version="1.0.0")
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://fazle.iamazim.com", "https://iamazim.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ───────────────────────────────────────────────────

class TaskType(str, Enum):
    research = "research"
    monitor = "monitor"
    reminder = "reminder"
    digest = "digest"
    learning = "learning"
    custom = "custom"


class TaskStatus(str, Enum):
    active = "active"
    paused = "paused"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class AutonomousTask(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    task_type: TaskType
    description: str
    trigger: str = "manual"  # "manual", "interval", "cron", "once"
    interval_minutes: Optional[int] = None
    status: TaskStatus = TaskStatus.active
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    run_count: int = 0
    last_result: Optional[str] = None
    last_error: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: Optional[str] = None
    user_id: Optional[str] = None
    config: dict[str, Any] = Field(default_factory=dict)


class CreateTaskRequest(BaseModel):
    name: str
    task_type: TaskType
    description: str
    trigger: str = "manual"
    interval_minutes: Optional[int] = None
    auto_start: bool = True
    user_id: Optional[str] = None
    config: dict[str, Any] = Field(default_factory=dict)


class TaskRunResult(BaseModel):
    task_id: str
    status: str
    result: Optional[str] = None
    error: Optional[str] = None
    duration_ms: int = 0
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# ── Task store & background handles ─────────────────────────

_tasks: dict[str, AutonomousTask] = {}
_run_history: list[TaskRunResult] = []
_background_handles: dict[str, asyncio.Task] = {}


# ── Task Execution Logic ────────────────────────────────────

async def _run_research(task: AutonomousTask) -> str:
    """Run a research task — search web, summarize, store in memory."""
    query = task.config.get("query", task.description)
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Search
        resp = await client.post(
            f"{settings.tools_url}/search",
            json={"query": query, "max_results": 5},
        )
        if resp.status_code != 200:
            return f"Search failed: {resp.status_code}"
        search_results = resp.text[:3000]

        # Summarize via LLM
        resp = await client.post(
            f"{settings.llm_gateway_url}/llm/generate",
            json={
                "prompt": f"Summarize these search results for the query '{query}':\n\n{search_results}",
                "system_prompt": "Provide a concise research summary.",
                "temperature": 0.3,
                "max_tokens": 500,
            },
        )
        summary = ""
        if resp.status_code == 200:
            data = resp.json()
            summary = data.get("response", data.get("text", search_results[:500]))

        # Store in memory
        await client.post(
            f"{settings.memory_url}/store",
            json={"content": f"Auto-research: {query}\n{summary}", "type": "autonomous_research"},
        )

        return summary


async def _run_monitor(task: AutonomousTask) -> str:
    """Monitor a topic — check for new info and alert if needed."""
    topic = task.config.get("topic", task.description)
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            f"{settings.tools_url}/search",
            json={"query": f"{topic} latest news today", "max_results": 3},
        )
        if resp.status_code == 200:
            return f"Monitor check complete: {resp.text[:1000]}"
        return f"Monitor check failed: {resp.status_code}"


async def _run_digest(task: AutonomousTask) -> str:
    """Generate a digest of recent memories and activities."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            f"{settings.memory_url}/search",
            json={"query": "recent activities today", "top_k": 10},
        )
        memories = resp.text[:3000] if resp.status_code == 200 else "No memories found"

        resp = await client.post(
            f"{settings.llm_gateway_url}/llm/generate",
            json={
                "prompt": f"Create a brief daily digest from these recent memories:\n\n{memories}",
                "system_prompt": "You are Fazle's digest generator. Create a concise daily summary.",
                "temperature": 0.3,
                "max_tokens": 500,
            },
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("response", data.get("text", "Digest generation incomplete"))
        return "Failed to generate digest"


async def _run_learning(task: AutonomousTask) -> str:
    """Trigger a learning cycle — analyze recent conversations."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{settings.memory_url}/search",
            json={"query": "conversation pattern preference", "top_k": 10},
        )
        context = resp.text[:2000] if resp.status_code == 200 else ""

        resp = await client.post(
            f"{settings.llm_gateway_url}/llm/generate",
            json={
                "prompt": f"Analyze these conversation patterns and identify learning opportunities:\n\n{context}",
                "system_prompt": "You are Fazle's self-improvement engine. Identify patterns, preferences, and areas for improvement.",
                "temperature": 0.3,
                "max_tokens": 500,
            },
        )
        if resp.status_code == 200:
            data = resp.json()
            insight = data.get("response", data.get("text", ""))
            # Store insight
            await client.post(
                f"{settings.memory_url}/store",
                json={"content": f"Self-learning insight: {insight}", "type": "self_learning"},
            )
            return insight
        return "Learning cycle incomplete"


async def _run_custom(task: AutonomousTask) -> str:
    """Run a custom task via the autonomy engine."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.autonomy_url}/autonomy/plan",
            json={
                "goal": task.description,
                "auto_execute": True,
                "context": json.dumps(task.config),
            },
        )
        if resp.status_code == 200:
            data = resp.json()
            return f"Autonomy plan created: {data.get('message', 'ok')}"
        return f"Custom task failed: {resp.status_code}"


_task_executors = {
    TaskType.research: _run_research,
    TaskType.monitor: _run_monitor,
    TaskType.digest: _run_digest,
    TaskType.learning: _run_learning,
    TaskType.custom: _run_custom,
    TaskType.reminder: _run_digest,  # Reminders use digest-style
}


async def execute_task(task: AutonomousTask) -> TaskRunResult:
    """Execute a single autonomous task."""
    start = datetime.utcnow()
    executor = _task_executors.get(task.task_type, _run_custom)

    try:
        result = await asyncio.wait_for(
            executor(task),
            timeout=settings.max_task_runtime_seconds,
        )
        elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)
        task.last_run = datetime.utcnow().isoformat()
        task.last_result = result[:2000] if result else None
        task.last_error = None
        task.run_count += 1
        task.updated_at = datetime.utcnow().isoformat()

        run_result = TaskRunResult(
            task_id=task.id, status="success", result=result[:2000], duration_ms=elapsed,
        )
        _run_history.append(run_result)
        return run_result

    except asyncio.TimeoutError:
        elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)
        task.last_error = "Task timed out"
        task.updated_at = datetime.utcnow().isoformat()
        run_result = TaskRunResult(
            task_id=task.id, status="timeout", error="Task timed out", duration_ms=elapsed,
        )
        _run_history.append(run_result)
        return run_result

    except Exception as e:
        elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)
        task.last_error = str(e)[:500]
        task.updated_at = datetime.utcnow().isoformat()
        logger.error(f"Task {task.id} failed: {e}")
        run_result = TaskRunResult(
            task_id=task.id, status="error", error=str(e)[:500], duration_ms=elapsed,
        )
        _run_history.append(run_result)
        return run_result


# ── Background Loop ─────────────────────────────────────────

async def _task_loop(task_id: str):
    """Background loop for interval-triggered tasks."""
    while True:
        task = _tasks.get(task_id)
        if not task or task.status != TaskStatus.active:
            break

        await execute_task(task)

        interval = task.interval_minutes or settings.default_interval_minutes
        await asyncio.sleep(interval * 60)


def _start_background(task: AutonomousTask):
    """Start a background loop for an interval task."""
    if task.id in _background_handles:
        _background_handles[task.id].cancel()
    handle = asyncio.create_task(_task_loop(task.id))
    _background_handles[task.id] = handle


def _stop_background(task_id: str):
    """Stop a background task loop."""
    handle = _background_handles.pop(task_id, None)
    if handle:
        handle.cancel()


# ── Endpoints ────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "autonomous-runner",
        "active_tasks": sum(1 for t in _tasks.values() if t.status == TaskStatus.active),
        "total_tasks": len(_tasks),
    }


@app.post("/tasks/autonomous")
async def create_autonomous_task(req: CreateTaskRequest):
    """Create a new autonomous task."""
    task = AutonomousTask(
        name=req.name,
        task_type=req.task_type,
        description=req.description,
        trigger=req.trigger,
        interval_minutes=req.interval_minutes,
        user_id=req.user_id,
        config=req.config,
    )
    _tasks[task.id] = task

    # Start background loop for interval tasks
    if req.auto_start and req.trigger == "interval" and req.interval_minutes:
        _start_background(task)

    # Execute immediately for "once" or "manual" with auto_start
    if req.auto_start and req.trigger in ("once", "manual"):
        result = await execute_task(task)
        if req.trigger == "once":
            task.status = TaskStatus.completed
        return {"task": task, "initial_result": result}

    return {"task": task, "message": "Task created"}


@app.get("/tasks/autonomous/history")
async def task_history(task_id: Optional[str] = None, limit: int = 50):
    """Get task execution history."""
    history = _run_history
    if task_id:
        history = [r for r in history if r.task_id == task_id]
    return {"history": history[-limit:], "total": len(history)}


@app.post("/tasks/autonomous/{task_id}/run")
async def run_task(task_id: str):
    """Manually trigger a task execution."""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    result = await execute_task(task)
    return {"task_id": task_id, "result": result}


@app.get("/tasks/autonomous/{task_id}")
async def get_task(task_id: str):
    """Get task details."""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.get("/tasks/autonomous")
async def list_tasks(
    status: Optional[str] = None,
    task_type: Optional[str] = None,
    limit: int = Query(default=50, le=200),
):
    """List autonomous tasks."""
    tasks = list(_tasks.values())
    if status:
        tasks = [t for t in tasks if t.status == status]
    if task_type:
        tasks = [t for t in tasks if t.task_type == task_type]
    tasks.sort(key=lambda t: t.created_at, reverse=True)
    return {"tasks": tasks[:limit], "total": len(tasks)}


@app.post("/tasks/autonomous/{task_id}/pause")
async def pause_task(task_id: str):
    """Pause an active task."""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = TaskStatus.paused
    task.updated_at = datetime.utcnow().isoformat()
    _stop_background(task_id)
    return {"message": "Task paused", "task_id": task_id}


@app.post("/tasks/autonomous/{task_id}/resume")
async def resume_task(task_id: str):
    """Resume a paused task."""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = TaskStatus.active
    task.updated_at = datetime.utcnow().isoformat()
    if task.trigger == "interval" and task.interval_minutes:
        _start_background(task)
    return {"message": "Task resumed", "task_id": task_id}


@app.delete("/tasks/autonomous/{task_id}")
async def cancel_task(task_id: str):
    """Cancel and remove a task."""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    _stop_background(task_id)
    task.status = TaskStatus.cancelled
    del _tasks[task_id]
    return {"message": "Task cancelled", "task_id": task_id}
