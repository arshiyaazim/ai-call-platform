# ============================================================
# Fazle Task Engine v2 — Scheduling, automation, event triggers
# ============================================================
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from prometheus_fastapi_instrumentator import Instrumentator
import asyncio
import httpx
import json
import logging
import os
import uuid
from typing import Optional, List
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fazle-task-engine")


class Settings(BaseSettings):
    brain_url: str = "http://fazle-brain:8200"
    memory_url: str = "http://fazle-memory:8300"
    dograh_api_url: str = "http://dograh-api:8000"
    database_url: str = ""

    class Config:
        env_prefix = "FAZLE_"


settings = Settings()

# ── Database setup ──────────────────────────────────────────
DATABASE_URL = settings.database_url or os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@postgres:5432/postgres",
)

engine = create_engine(DATABASE_URL)


def ensure_tables():
    """Create task and scheduler tables if they don't exist (idempotent)."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS fazle_tasks (
                id VARCHAR(36) PRIMARY KEY,
                title VARCHAR(500) NOT NULL,
                description TEXT DEFAULT '',
                task_type VARCHAR(50) NOT NULL DEFAULT 'reminder',
                status VARCHAR(50) NOT NULL DEFAULT 'pending',
                scheduled_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                payload JSONB DEFAULT '{}'::jsonb,
                recurrence VARCHAR(200) DEFAULT NULL,
                last_run TIMESTAMPTZ DEFAULT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS fazle_event_triggers (
                id VARCHAR(36) PRIMARY KEY,
                event_type VARCHAR(100) NOT NULL,
                condition JSONB DEFAULT '{}'::jsonb,
                action_task_id VARCHAR(36) REFERENCES fazle_tasks(id) ON DELETE CASCADE,
                enabled BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
        # Add columns if they don't exist (for existing deployments)
        for col, coltype in [("recurrence", "VARCHAR(200)"), ("last_run", "TIMESTAMPTZ")]:
            try:
                conn.execute(text(f"ALTER TABLE fazle_tasks ADD COLUMN IF NOT EXISTS {col} {coltype}"))
            except Exception:
                pass
        conn.commit()
    logger.info("Database tables verified")


app = FastAPI(title="Fazle Task Engine — Scheduling & Automation", version="2.0.0")

Instrumentator().instrument(app).expose(app, endpoint="/metrics")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "https://fazle.iamazim.com,https://iamazim.com,http://localhost:3020").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

jobstores = {"default": SQLAlchemyJobStore(engine=engine)}
scheduler = AsyncIOScheduler(
    jobstores=jobstores,
    job_defaults={"misfire_grace_time": 300, "coalesce": True},
)

TASK_TYPES = {"reminder", "call", "summary", "instruction", "custom", "monitor", "learning_update", "follow_up", "recurring"}


@app.on_event("startup")
async def startup():
    ensure_tables()
    scheduler.start()
    logger.info("Task scheduler started with PostgreSQL job store")


@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown()


# ── Health ──────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "fazle-task-engine", "timestamp": datetime.utcnow().isoformat()}


# ── Task models ─────────────────────────────────────────────
class TaskCreateRequest(BaseModel):
    title: str
    description: str = ""
    scheduled_at: Optional[str] = None
    task_type: str = "reminder"
    payload: dict = Field(default_factory=dict)
    recurrence: Optional[str] = None  # cron expression or interval like "every 1h", "every 30m"


class TaskResponse(BaseModel):
    id: str
    title: str
    description: str
    task_type: str
    status: str
    scheduled_at: Optional[str]
    created_at: str
    payload: dict
    recurrence: Optional[str] = None
    last_run: Optional[str] = None


class EventTriggerCreate(BaseModel):
    event_type: str  # e.g. "voice_call_ended", "memory_stored", "daily_summary"
    condition: dict = Field(default_factory=dict)  # JSON condition e.g. {"min_duration": 60}
    action_task_id: str  # task to execute when triggered


class EventTriggerResponse(BaseModel):
    id: str
    event_type: str
    condition: dict
    action_task_id: str
    enabled: bool
    created_at: str


# ── Create task ─────────────────────────────────────────────
@app.post("/tasks", response_model=TaskResponse)
async def create_task(request: TaskCreateRequest):
    """Create a new scheduled task, recurring task, or reminder."""
    if request.task_type not in TASK_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid task type. Must be one of: {TASK_TYPES}")

    task_id = str(uuid.uuid4())
    now = datetime.utcnow()

    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO fazle_tasks (id, title, description, task_type, status, scheduled_at, created_at, payload, recurrence)
                VALUES (:id, :title, :description, :task_type, 'pending', :scheduled_at, :created_at, :payload, :recurrence)
            """),
            {
                "id": task_id,
                "title": request.title,
                "description": request.description,
                "task_type": request.task_type,
                "scheduled_at": request.scheduled_at,
                "created_at": now.isoformat(),
                "payload": json.dumps(request.payload),
                "recurrence": request.recurrence,
            },
        )
        conn.commit()

    # Schedule recurring tasks
    if request.recurrence:
        trigger = _parse_recurrence(request.recurrence)
        if trigger:
            scheduler.add_job(
                _execute_task,
                trigger=trigger,
                args=[task_id],
                id=task_id,
                replace_existing=True,
            )
            logger.info(f"Recurring task {task_id} scheduled: {request.recurrence}")
    elif request.scheduled_at:
        try:
            trigger_time = datetime.fromisoformat(request.scheduled_at)
            scheduler.add_job(
                _execute_task,
                trigger=DateTrigger(run_date=trigger_time),
                args=[task_id],
                id=task_id,
                replace_existing=True,
            )
            logger.info(f"Task {task_id} scheduled for {request.scheduled_at}")
        except ValueError:
            logger.warning(f"Invalid schedule time: {request.scheduled_at}")

    return TaskResponse(
        id=task_id,
        title=request.title,
        description=request.description,
        task_type=request.task_type,
        status="pending",
        scheduled_at=request.scheduled_at,
        created_at=now.isoformat(),
        payload=request.payload,
        recurrence=request.recurrence,
    )


def _parse_recurrence(recurrence: str):
    """Parse a recurrence string into an APScheduler trigger."""
    rec = recurrence.strip().lower()
    # Interval patterns: "every 1h", "every 30m", "every 2d"
    if rec.startswith("every "):
        part = rec[6:].strip()
        if part.endswith("m"):
            minutes = int(part[:-1])
            return IntervalTrigger(minutes=minutes)
        elif part.endswith("h"):
            hours = int(part[:-1])
            return IntervalTrigger(hours=hours)
        elif part.endswith("d"):
            days = int(part[:-1])
            return IntervalTrigger(days=days)
    # Cron expression: "0 9 * * *" (daily at 9am)
    parts = rec.split()
    if len(parts) == 5:
        try:
            return CronTrigger(
                minute=parts[0], hour=parts[1], day=parts[2],
                month=parts[3], day_of_week=parts[4],
            )
        except Exception:
            pass
    logger.warning(f"Could not parse recurrence: {recurrence}")
    return None


# ── List tasks ──────────────────────────────────────────────
@app.get("/tasks")
async def list_tasks(status: Optional[str] = None, task_type: Optional[str] = None):
    """List all tasks, optionally filtered."""
    query = "SELECT id, title, description, task_type, status, scheduled_at, created_at, payload, recurrence, last_run FROM fazle_tasks WHERE 1=1"
    params: dict = {}
    if status:
        query += " AND status = :status"
        params["status"] = status
    if task_type:
        query += " AND task_type = :task_type"
        params["task_type"] = task_type
    query += " ORDER BY created_at DESC"

    with engine.connect() as conn:
        rows = conn.execute(text(query), params).mappings().all()

    result = [_row_to_dict(r) for r in rows]
    return {"tasks": result, "count": len(result)}


def _row_to_dict(row) -> dict:
    """Convert a DB row mapping to a task dict."""
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"] or "",
        "task_type": row["task_type"],
        "status": row["status"],
        "scheduled_at": row["scheduled_at"].isoformat() if row["scheduled_at"] else None,
        "created_at": row["created_at"].isoformat() if row["created_at"] else "",
        "payload": row["payload"] if isinstance(row["payload"], dict) else json.loads(row["payload"] or "{}"),
        "recurrence": row.get("recurrence"),
        "last_run": row["last_run"].isoformat() if row.get("last_run") else None,
    }


# ── Get task ────────────────────────────────────────────────
@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, title, description, task_type, status, scheduled_at, created_at, payload, recurrence, last_run FROM fazle_tasks WHERE id = :id"),
            {"id": task_id},
        ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse(**_row_to_dict(row))


# ── Update task status ──────────────────────────────────────
class TaskUpdateRequest(BaseModel):
    status: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None


@app.patch("/tasks/{task_id}")
async def update_task(task_id: str, request: TaskUpdateRequest):
    sets = []
    params: dict = {"id": task_id}
    if request.status:
        sets.append("status = :status")
        params["status"] = request.status
    if request.title:
        sets.append("title = :title")
        params["title"] = request.title
    if request.description:
        sets.append("description = :description")
        params["description"] = request.description

    if not sets:
        raise HTTPException(status_code=400, detail="No fields to update")

    with engine.connect() as conn:
        result = conn.execute(
            text(f"UPDATE fazle_tasks SET {', '.join(sets)} WHERE id = :id RETURNING *"),
            params,
        ).mappings().first()
        conn.commit()

    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return _row_to_dict(result)


# ── Delete task ─────────────────────────────────────────────
@app.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    # Remove scheduled job if exists
    try:
        scheduler.remove_job(task_id)
    except Exception:
        pass

    with engine.connect() as conn:
        result = conn.execute(text("DELETE FROM fazle_tasks WHERE id = :id RETURNING id"), {"id": task_id}).first()
        conn.commit()

    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "deleted", "id": task_id}


# ── Task execution ─────────────────────────────────────────
def _get_task_row(task_id: str):
    """Fetch a task row from DB (sync — called via asyncio.to_thread)."""
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT id, title, description, task_type, status, scheduled_at, created_at, payload, recurrence, last_run FROM fazle_tasks WHERE id = :id"),
            {"id": task_id},
        ).mappings().first()


async def _execute_task(task_id: str):
    """Execute a scheduled task (offloads sync DB calls to thread pool)."""
    row = await asyncio.to_thread(_get_task_row, task_id)
    if not row:
        logger.warning(f"Task {task_id} not found in database, skipping execution")
        return

    task = _row_to_dict(row)
    await asyncio.to_thread(_update_task_status, task_id, "executing")
    logger.info(f"Executing task: {task['title']} ({task['task_type']})")

    try:
        if task["task_type"] == "reminder":
            await _handle_reminder(task)
        elif task["task_type"] == "call":
            await _handle_call_task(task)
        elif task["task_type"] == "summary":
            await _handle_summary(task)
        elif task["task_type"] == "monitor":
            await _handle_monitor(task)
        elif task["task_type"] == "learning_update":
            await _handle_learning_update(task)
        elif task["task_type"] == "follow_up":
            await _handle_follow_up(task)

        # For recurring tasks, reset to pending and track last_run
        if task.get("recurrence"):
            await asyncio.to_thread(_mark_recurring_run, task_id)
        else:
            await asyncio.to_thread(_update_task_status, task_id, "completed")
        logger.info(f"Task {task_id} completed successfully")
    except Exception as e:
        logger.error(f"Task {task_id} execution failed: {e}", exc_info=True)
        await asyncio.to_thread(_update_task_status, task_id, "failed")


def _update_task_status(task_id: str, status: str):
    """Update task status in the database (sync — called via asyncio.to_thread)."""
    with engine.connect() as conn:
        conn.execute(text("UPDATE fazle_tasks SET status = :status WHERE id = :id"), {"id": task_id, "status": status})
        conn.commit()


async def _handle_reminder(task: dict):
    """Store reminder result in memory."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(
                f"{settings.memory_url}/store",
                json={
                    "type": "personal",
                    "user": "Azim",
                    "content": {"task_id": task["id"], "reminder": task["title"]},
                    "text": f"Reminder: {task['title']}. {task['description']}",
                },
            )
        except Exception as e:
            logger.warning(f"Failed to store reminder: {e}")


async def _handle_call_task(task: dict):
    """Trigger an outbound call via Dograh."""
    logger.info(f"Call task: {task['title']} — would trigger Dograh outbound call")


async def _handle_summary(task: dict):
    """Generate a summary using the brain."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            await client.post(
                f"{settings.brain_url}/chat",
                json={
                    "message": f"Generate a summary for: {task['description']}",
                    "user": "Azim",
                },
            )
        except Exception as e:
            logger.warning(f"Summary generation failed: {e}")


def _mark_recurring_run(task_id: str):
    """Update last_run and reset status for recurring tasks."""
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE fazle_tasks SET status = 'pending', last_run = NOW() WHERE id = :id"),
            {"id": task_id},
        )
        conn.commit()


async def _handle_monitor(task: dict):
    """Run a monitoring check (e.g., service health, watchdog)."""
    payload = task.get("payload", {})
    url = payload.get("check_url")
    if not url:
        logger.warning(f"Monitor task {task['id']} has no check_url in payload")
        return
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(url)
            result = {"status_code": resp.status_code, "healthy": resp.status_code < 400}
            logger.info(f"Monitor {task['title']}: {result}")
            # Store result in memory
            await client.post(
                f"{settings.memory_url}/store",
                json={
                    "type": "system",
                    "user": "Azim",
                    "content": {"task_id": task["id"], "monitor": result},
                    "text": f"Monitor check '{task['title']}': status={resp.status_code}",
                },
            )
        except Exception as e:
            logger.warning(f"Monitor check failed: {e}")


async def _handle_learning_update(task: dict):
    """Trigger a learning/training cycle via the brain."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            await client.post(
                f"{settings.brain_url}/chat",
                json={
                    "message": f"Learning update: Review and consolidate recent interactions. {task['description']}",
                    "user": "Azim",
                },
            )
        except Exception as e:
            logger.warning(f"Learning update failed: {e}")


async def _handle_follow_up(task: dict):
    """Send a follow-up reminder or action."""
    payload = task.get("payload", {})
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            await client.post(
                f"{settings.memory_url}/store",
                json={
                    "type": "personal",
                    "user": "Azim",
                    "content": {"task_id": task["id"], "follow_up": task["title"], "context": payload},
                    "text": f"Follow-up: {task['title']}. {task['description']}",
                },
            )
        except Exception as e:
            logger.warning(f"Follow-up store failed: {e}")


# ── Event Triggers ──────────────────────────────────────────
@app.post("/triggers", response_model=EventTriggerResponse)
async def create_trigger(request: EventTriggerCreate):
    """Create an event trigger that fires a task when an event occurs."""
    # Verify the task exists
    with engine.connect() as conn:
        task_exists = conn.execute(
            text("SELECT id FROM fazle_tasks WHERE id = :id"), {"id": request.action_task_id}
        ).first()
    if not task_exists:
        raise HTTPException(status_code=404, detail="Action task not found")

    trigger_id = str(uuid.uuid4())
    now = datetime.utcnow()
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO fazle_event_triggers (id, event_type, condition, action_task_id, enabled, created_at)
                VALUES (:id, :event_type, :condition, :action_task_id, TRUE, :created_at)
            """),
            {
                "id": trigger_id,
                "event_type": request.event_type,
                "condition": json.dumps(request.condition),
                "action_task_id": request.action_task_id,
                "created_at": now.isoformat(),
            },
        )
        conn.commit()

    return EventTriggerResponse(
        id=trigger_id,
        event_type=request.event_type,
        condition=request.condition,
        action_task_id=request.action_task_id,
        enabled=True,
        created_at=now.isoformat(),
    )


@app.get("/triggers")
async def list_triggers(event_type: Optional[str] = None):
    """List all event triggers."""
    query = "SELECT id, event_type, condition, action_task_id, enabled, created_at FROM fazle_event_triggers WHERE 1=1"
    params: dict = {}
    if event_type:
        query += " AND event_type = :event_type"
        params["event_type"] = event_type
    query += " ORDER BY created_at DESC"

    with engine.connect() as conn:
        rows = conn.execute(text(query), params).mappings().all()

    triggers = []
    for r in rows:
        triggers.append({
            "id": r["id"],
            "event_type": r["event_type"],
            "condition": r["condition"] if isinstance(r["condition"], dict) else json.loads(r["condition"] or "{}"),
            "action_task_id": r["action_task_id"],
            "enabled": r["enabled"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else "",
        })
    return {"triggers": triggers, "count": len(triggers)}


@app.delete("/triggers/{trigger_id}")
async def delete_trigger(trigger_id: str):
    """Delete an event trigger."""
    with engine.connect() as conn:
        result = conn.execute(
            text("DELETE FROM fazle_event_triggers WHERE id = :id RETURNING id"),
            {"id": trigger_id},
        ).first()
        conn.commit()
    if not result:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return {"status": "deleted", "id": trigger_id}


@app.post("/events/fire")
async def fire_event(event_type: str, event_data: dict = None):
    """Fire an event — all matching triggers will execute their tasks."""
    event_data = event_data or {}
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, condition, action_task_id FROM fazle_event_triggers WHERE event_type = :et AND enabled = TRUE"),
            {"et": event_type},
        ).mappings().all()

    fired = []
    for row in rows:
        condition = row["condition"] if isinstance(row["condition"], dict) else json.loads(row["condition"] or "{}")
        if _check_condition(condition, event_data):
            asyncio.create_task(_execute_task(row["action_task_id"]))
            fired.append({"trigger_id": row["id"], "task_id": row["action_task_id"]})

    return {"event_type": event_type, "triggers_fired": len(fired), "details": fired}


def _check_condition(condition: dict, event_data: dict) -> bool:
    """Check if event data satisfies trigger condition. Empty condition = always fire."""
    if not condition:
        return True
    for key, expected in condition.items():
        actual = event_data.get(key)
        if actual is None:
            return False
        if isinstance(expected, (int, float)):
            if not (isinstance(actual, (int, float)) and actual >= expected):
                return False
        elif actual != expected:
            return False
    return True
