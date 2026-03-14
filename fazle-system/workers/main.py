# ============================================================
# Fazle Workers — Redis Streams Consumer Pool
# Consumes LLM requests from the queue, calls the LLM Gateway,
# and stores results. Horizontally scalable via replicas.
# ============================================================
from fastapi import FastAPI
from pydantic_settings import BaseSettings
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter, Histogram, Gauge
import redis
import httpx
import json
import logging
import asyncio
import os
import signal
import time
from typing import Optional
from datetime import datetime
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fazle-workers")


class Settings(BaseSettings):
    redis_url: str = "redis://redis:6379/5"
    stream_name: str = "llm_requests"
    consumer_group: str = "llm_workers"
    consumer_name: str = f"worker-{os.getpid()}"
    llm_gateway_url: str = "http://fazle-llm-gateway:8800"
    queue_url: str = "http://fazle-queue:8810"
    # How many messages to read per batch
    batch_size: int = 5
    # Block timeout in ms when reading from stream
    block_ms: int = 2000
    # Max retries per task
    max_retries: int = 3
    # Claim pending messages older than this (ms)
    claim_min_idle_ms: int = 60000

    class Config:
        env_prefix = ""


settings = Settings()

_redis: Optional[redis.Redis] = None
_shutdown = False


def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


# ── Prometheus Metrics ──────────────────────────────────────

tasks_processed_total = Counter(
    "fazle_worker_tasks_processed_total",
    "Total tasks processed by this worker",
    ["status"],
)
llm_request_latency = Histogram(
    "fazle_worker_llm_latency_seconds",
    "Latency of LLM Gateway calls from workers",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
)
worker_active_tasks = Gauge(
    "fazle_worker_active_tasks",
    "Number of tasks currently being processed",
)
worker_idle = Gauge(
    "fazle_worker_idle",
    "1 if the worker is idle, 0 if processing",
)


# ── Core Worker Logic ───────────────────────────────────────

async def _process_task(task_id: str):
    """Fetch task data from Redis, call LLM Gateway, and report result."""
    r = _get_redis()
    task_key = f"task:{task_id}"

    task_data = r.hgetall(task_key)
    if not task_data:
        logger.warning(f"Task {task_id} not found in Redis, skipping")
        return

    # Mark as processing
    r.hset(task_key, "status", "processing")

    request_data = json.loads(task_data.get("request", "{}"))

    # Call LLM Gateway
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                f"{settings.llm_gateway_url}/generate",
                json={
                    "messages": request_data.get("messages", []),
                    "provider": request_data.get("provider"),
                    "model": request_data.get("model"),
                    "temperature": request_data.get("temperature", 0.7),
                    "response_format": request_data.get("response_format"),
                    "caller": request_data.get("caller", "worker"),
                    "stream": False,
                    "cache": request_data.get("cache", True),
                },
            )
            latency = time.monotonic() - start
            llm_request_latency.observe(latency)

            if resp.status_code == 200:
                result = resp.json()
                # Report success to queue service
                async with httpx.AsyncClient(timeout=10.0) as qclient:
                    await qclient.post(
                        f"{settings.queue_url}/task/{task_id}/complete",
                        json=result,
                    )
                tasks_processed_total.labels(status="success").inc()
                logger.info(f"Task {task_id} completed in {latency:.1f}s")
            else:
                error_detail = resp.text[:500]
                async with httpx.AsyncClient(timeout=10.0) as qclient:
                    await qclient.post(
                        f"{settings.queue_url}/task/{task_id}/fail",
                        json={"detail": f"LLM Gateway returned {resp.status_code}: {error_detail}"},
                    )
                tasks_processed_total.labels(status="failed").inc()
                logger.error(f"Task {task_id} failed: gateway returned {resp.status_code}")

    except Exception as e:
        latency = time.monotonic() - start
        llm_request_latency.observe(latency)
        logger.error(f"Task {task_id} error: {e}")

        # Check retry count
        retries = int(task_data.get("retries", 0))
        if retries < settings.max_retries:
            r.hset(task_key, mapping={"status": "pending", "retries": str(retries + 1)})
            # Re-add to stream for retry
            r.xadd(
                settings.stream_name,
                {"task_id": task_id, "priority": "5", "retry": str(retries + 1)},
                maxlen=10000,
            )
            logger.info(f"Task {task_id} re-queued for retry ({retries + 1}/{settings.max_retries})")
        else:
            try:
                async with httpx.AsyncClient(timeout=10.0) as qclient:
                    await qclient.post(
                        f"{settings.queue_url}/task/{task_id}/fail",
                        json={"detail": f"Max retries exceeded: {str(e)[:200]}"},
                    )
            except Exception:
                r.hset(task_key, mapping={
                    "status": "failed",
                    "error": f"Max retries exceeded: {str(e)[:200]}",
                    "completed_at": datetime.utcnow().isoformat(),
                })
            tasks_processed_total.labels(status="failed").inc()


async def _claim_stale_messages():
    """Claim messages that have been pending too long (worker crash recovery)."""
    r = _get_redis()
    try:
        pending = r.xpending_range(
            settings.stream_name,
            settings.consumer_group,
            min="-",
            max="+",
            count=10,
        )
        for entry in pending:
            idle_ms = entry.get("time_since_delivered", 0)
            if idle_ms > settings.claim_min_idle_ms:
                msg_id = entry["message_id"]
                claimed = r.xclaim(
                    settings.stream_name,
                    settings.consumer_group,
                    settings.consumer_name,
                    min_idle_time=settings.claim_min_idle_ms,
                    message_ids=[msg_id],
                )
                for msg in claimed:
                    task_id = msg[1].get("task_id")
                    if task_id:
                        logger.info(f"Claimed stale task {task_id} (idle {idle_ms}ms)")
                        worker_active_tasks.inc()
                        try:
                            await _process_task(task_id)
                        finally:
                            worker_active_tasks.dec()
                        r.xack(settings.stream_name, settings.consumer_group, msg_id)
    except redis.ResponseError:
        pass
    except Exception as e:
        logger.debug(f"Claim check error: {e}")


async def _consumer_loop():
    """Main consumer loop — reads from Redis Stream and processes tasks."""
    global _shutdown
    r = _get_redis()

    # Ensure consumer group exists
    try:
        r.xgroup_create(settings.stream_name, settings.consumer_group, id="0", mkstream=True)
    except redis.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise

    logger.info(f"Worker {settings.consumer_name} started, consuming from '{settings.stream_name}'")

    while not _shutdown:
        try:
            worker_idle.set(1)

            # Read new messages
            messages = r.xreadgroup(
                settings.consumer_group,
                settings.consumer_name,
                {settings.stream_name: ">"},
                count=settings.batch_size,
                block=settings.block_ms,
            )

            if not messages:
                # No new messages — try claiming stale ones
                await _claim_stale_messages()
                await asyncio.sleep(0.1)
                continue

            worker_idle.set(0)

            for stream_name, entries in messages:
                for msg_id, fields in entries:
                    task_id = fields.get("task_id")
                    if not task_id:
                        r.xack(settings.stream_name, settings.consumer_group, msg_id)
                        continue

                    worker_active_tasks.inc()
                    try:
                        await _process_task(task_id)
                    finally:
                        worker_active_tasks.dec()

                    # Acknowledge the message
                    r.xack(settings.stream_name, settings.consumer_group, msg_id)

        except redis.ConnectionError:
            logger.warning("Redis connection lost, reconnecting in 5s...")
            global _redis
            _redis = None
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Consumer loop error: {e}")
            await asyncio.sleep(1)

    logger.info(f"Worker {settings.consumer_name} shutting down")


# ── Application Lifecycle ───────────────────────────────────

_consumer_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _consumer_task, _shutdown
    _shutdown = False
    _consumer_task = asyncio.create_task(_consumer_loop())
    logger.info("Consumer loop started")
    yield
    _shutdown = True
    if _consumer_task:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
    logger.info("Consumer loop stopped")


app = FastAPI(title="Fazle Worker", version="1.0.0", lifespan=lifespan)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")


@app.get("/health")
async def health():
    healthy = True
    checks = {}

    # Check Redis
    try:
        _get_redis().ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"
        healthy = False

    # Check consumer loop
    if _consumer_task and not _consumer_task.done():
        checks["consumer"] = "running"
    else:
        checks["consumer"] = "stopped"
        healthy = False

    return {
        "status": "healthy" if healthy else "degraded",
        "service": "fazle-worker",
        "worker_name": settings.consumer_name,
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/worker/stats")
async def worker_stats():
    """Return worker-specific statistics."""
    r = _get_redis()
    try:
        groups = r.xinfo_groups(settings.stream_name)
        pending_count = 0
        for g in groups:
            if g.get("name") == settings.consumer_group:
                pending_count = g.get("pending", 0)
                break
        stream_info = r.xinfo_stream(settings.stream_name)
        stream_length = stream_info.get("length", 0)
    except Exception:
        pending_count = 0
        stream_length = 0

    return {
        "worker_name": settings.consumer_name,
        "stream_length": stream_length,
        "group_pending": pending_count,
        "timestamp": datetime.utcnow().isoformat(),
    }
