# ============================================================
# Fazle Queue — Redis Streams-Based Async Request Queue
# Accepts LLM requests, enqueues via Redis Streams, and
# exposes status polling + Prometheus metrics
# ============================================================
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Gauge, Counter
import redis
import json
import logging
import uuid
import os
from typing import Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fazle-queue")


class Settings(BaseSettings):
    redis_url: str = "redis://redis:6379/5"
    stream_name: str = "llm_requests"
    result_ttl: int = 600  # seconds to keep completed results
    max_stream_len: int = 10000  # cap stream length

    class Config:
        env_prefix = ""


settings = Settings()

_redis: Optional[redis.Redis] = None


def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


app = FastAPI(title="Fazle Queue", version="1.0.0")

Instrumentator().instrument(app).expose(app, endpoint="/metrics")

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "https://fazle.iamazim.com,https://iamazim.com,http://localhost:3020",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Prometheus Metrics ──────────────────────────────────────

queue_length_gauge = Gauge(
    "fazle_queue_length",
    "Number of pending messages in the LLM request stream",
)
tasks_enqueued_total = Counter(
    "fazle_tasks_enqueued_total",
    "Total tasks enqueued",
)
tasks_completed_total = Counter(
    "fazle_tasks_completed_total",
    "Total tasks completed (reported by workers)",
)
tasks_failed_total = Counter(
    "fazle_tasks_failed_total",
    "Total tasks failed",
)


def _update_queue_gauge():
    """Update queue length gauge from stream info."""
    try:
        r = _get_redis()
        info = r.xinfo_stream(settings.stream_name)
        queue_length_gauge.set(info.get("length", 0))
    except redis.ResponseError:
        queue_length_gauge.set(0)
    except Exception:
        pass


# ── Request / Response Models ───────────────────────────────

class EnqueueRequest(BaseModel):
    messages: list[dict] = Field(..., description="Chat messages array")
    provider: Optional[str] = Field(None, description="Override provider")
    model: Optional[str] = Field(None, description="Override model name")
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    response_format: Optional[str] = Field(None, description="'json' for JSON mode")
    caller: str = Field("unknown", description="Calling service name")
    cache: bool = Field(True, description="Use response cache")
    priority: int = Field(5, ge=1, le=10, description="Priority 1=highest 10=lowest")


class EnqueueResponse(BaseModel):
    task_id: str
    status: str = "pending"
    position: int = 0


class TaskStatus(BaseModel):
    task_id: str
    status: str  # pending | processing | completed | failed
    result: Optional[dict] = None
    error: Optional[str] = None
    enqueued_at: Optional[str] = None
    completed_at: Optional[str] = None
    latency_ms: Optional[float] = None


# ── Endpoints ───────────────────────────────────────────────

@app.get("/health")
async def health():
    healthy = True
    checks = {}
    try:
        _get_redis().ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"
        healthy = False
    body = {
        "status": "healthy" if healthy else "degraded",
        "service": "fazle-queue",
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat(),
    }
    return JSONResponse(content=body, status_code=200 if healthy else 503)


@app.post("/enqueue", response_model=EnqueueResponse)
async def enqueue(request: EnqueueRequest):
    """Submit an LLM request to the async processing queue."""
    r = _get_redis()
    task_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    # Store task metadata
    task_key = f"task:{task_id}"
    task_data = {
        "task_id": task_id,
        "status": "pending",
        "enqueued_at": now,
        "request": json.dumps({
            "messages": request.messages,
            "provider": request.provider,
            "model": request.model,
            "temperature": request.temperature,
            "response_format": request.response_format,
            "caller": request.caller,
            "cache": request.cache,
        }),
    }
    r.hset(task_key, mapping=task_data)
    r.expire(task_key, settings.result_ttl)

    # Add to Redis Stream
    r.xadd(
        settings.stream_name,
        {"task_id": task_id, "priority": str(request.priority)},
        maxlen=settings.max_stream_len,
    )

    tasks_enqueued_total.inc()
    _update_queue_gauge()

    # Approximate position
    try:
        info = r.xinfo_stream(settings.stream_name)
        position = info.get("length", 0)
    except Exception:
        position = 0

    return EnqueueResponse(task_id=task_id, status="pending", position=position)


@app.get("/status/{task_id}", response_model=TaskStatus)
async def get_status(task_id: str):
    """Poll for the status/result of an enqueued task."""
    r = _get_redis()
    task_key = f"task:{task_id}"

    if not r.exists(task_key):
        raise HTTPException(status_code=404, detail="Task not found or expired")

    data = r.hgetall(task_key)
    result = None
    if data.get("result"):
        result = json.loads(data["result"])

    latency_ms = None
    if data.get("enqueued_at") and data.get("completed_at"):
        try:
            t0 = datetime.fromisoformat(data["enqueued_at"])
            t1 = datetime.fromisoformat(data["completed_at"])
            latency_ms = (t1 - t0).total_seconds() * 1000
        except Exception:
            pass

    return TaskStatus(
        task_id=task_id,
        status=data.get("status", "unknown"),
        result=result,
        error=data.get("error"),
        enqueued_at=data.get("enqueued_at"),
        completed_at=data.get("completed_at"),
        latency_ms=latency_ms,
    )


@app.get("/queue/info")
async def queue_info():
    """Return queue statistics."""
    r = _get_redis()
    try:
        info = r.xinfo_stream(settings.stream_name)
        groups = r.xinfo_groups(settings.stream_name)
    except redis.ResponseError:
        return {"length": 0, "groups": [], "stream_exists": False}

    group_info = []
    for g in groups:
        group_info.append({
            "name": g.get("name"),
            "consumers": g.get("consumers", 0),
            "pending": g.get("pending", 0),
            "last_delivered_id": g.get("last-delivered-id", "0-0"),
        })

    _update_queue_gauge()

    return {
        "stream_exists": True,
        "length": info.get("length", 0),
        "first_entry": info.get("first-entry"),
        "last_entry": info.get("last-entry"),
        "groups": group_info,
    }


@app.post("/task/{task_id}/complete")
async def mark_complete(task_id: str, result: dict):
    """Called by workers to mark a task as completed (internal API)."""
    r = _get_redis()
    task_key = f"task:{task_id}"

    if not r.exists(task_key):
        raise HTTPException(status_code=404, detail="Task not found")

    now = datetime.utcnow().isoformat()
    r.hset(task_key, mapping={
        "status": "completed",
        "result": json.dumps(result),
        "completed_at": now,
    })
    r.expire(task_key, settings.result_ttl)
    tasks_completed_total.inc()
    _update_queue_gauge()
    return {"ok": True}


@app.post("/task/{task_id}/fail")
async def mark_failed(task_id: str, error: dict):
    """Called by workers to mark a task as failed (internal API)."""
    r = _get_redis()
    task_key = f"task:{task_id}"

    if not r.exists(task_key):
        raise HTTPException(status_code=404, detail="Task not found")

    now = datetime.utcnow().isoformat()
    r.hset(task_key, mapping={
        "status": "failed",
        "error": error.get("detail", "Unknown error"),
        "completed_at": now,
    })
    r.expire(task_key, settings.result_ttl)
    tasks_failed_total.inc()
    _update_queue_gauge()
    return {"ok": True}


@app.on_event("startup")
async def startup():
    """Ensure the consumer group exists."""
    r = _get_redis()
    try:
        r.xgroup_create(settings.stream_name, "llm_workers", id="0", mkstream=True)
        logger.info(f"Created consumer group 'llm_workers' on stream '{settings.stream_name}'")
    except redis.ResponseError as e:
        if "BUSYGROUP" in str(e):
            logger.info("Consumer group 'llm_workers' already exists")
        else:
            raise
