#!/usr/bin/env python3
"""
AI Watchdog — Self-Healing Infrastructure Controller
Monitors containers, disk, queue, logs, and metrics.
Performs automatic repairs with safety limits.
"""

import os
import sys
import time
import json
import signal
import logging
import subprocess
from datetime import datetime, timedelta

import yaml
import docker
import redis
import requests

# ── Logging ──────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("watchdog")

# ── Config ───────────────────────────────────────────────────

CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config.yaml")

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

CFG = load_config()

CHECK_INTERVAL   = CFG.get("check_interval", 30)
DISK_WARNING     = CFG.get("disk_warning", 75)
DISK_CRITICAL    = CFG.get("disk_critical", 85)
QUEUE_SCALE_UP   = CFG.get("queue_scale_up", 50)
QUEUE_SCALE_DOWN = CFG.get("queue_scale_down", 10)
WORKERS_MIN      = CFG.get("workers_min", 2)
WORKERS_MAX      = CFG.get("workers_max", 4)
REDIS_DB         = CFG.get("redis_db", 5)
REDIS_STREAM     = CFG.get("redis_stream", "llm_requests")
COMPOSE_FILE     = CFG.get("compose_file", "/home/azim/ai-call-platform/fazle-ai/docker-compose.yaml")
ENV_FILE         = CFG.get("env_file", "/home/azim/ai-call-platform/.env")
LOG_CONTAINERS   = CFG.get("log_containers", ["fazle-api", "fazle-voice"])
MONITORED        = CFG.get("monitored_containers", [])

OLLAMA_URL       = os.getenv("OLLAMA_URL", "http://ollama:11434")
PROMETHEUS_URL   = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
REDIS_HOST       = os.getenv("REDIS_HOST", "ai-redis")
REDIS_PASSWORD   = os.getenv("REDIS_PASSWORD", "")

# Safety: track restart attempts per container to prevent loops
restart_counts: dict[str, int] = {}
restart_reset_time: dict[str, datetime] = {}
MAX_RESTARTS_PER_HOUR = 3
CPU_HIGH_SINCE: dict[str, datetime] = {}

# Graceful shutdown
shutdown = False

def handle_signal(signum, frame):
    global shutdown
    log.info("Received signal %d, shutting down gracefully...", signum)
    shutdown = True

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

# ── Docker Client ────────────────────────────────────────────

client = docker.from_env()

# ── 1. Container Health Monitor ──────────────────────────────

def check_containers():
    """Check all monitored containers are running. Restart if down."""
    log.info("── Container Health Check ──")
    all_containers = {c.name: c for c in client.containers.list(all=True)}

    for name in MONITORED:
        container = all_containers.get(name)
        if container is None:
            log.warning("Container %s not found at all — skipping (may need compose up)", name)
            continue

        status = container.status
        if status == "running":
            # Check health if available
            health = container.attrs.get("State", {}).get("Health", {})
            health_status = health.get("Status", "none")
            if health_status == "unhealthy":
                log.warning("Container %s is UNHEALTHY — attempting restart", name)
                safe_restart(name, container)
            continue

        log.warning("Container %s status=%s — attempting restart", name, status)
        safe_restart(name, container)


def safe_restart(name, container):
    """Restart a container with rate limiting to prevent restart loops."""
    now = datetime.now()

    # Reset counter if more than 1 hour since last restart
    if name in restart_reset_time:
        if now - restart_reset_time[name] > timedelta(hours=1):
            restart_counts[name] = 0

    count = restart_counts.get(name, 0)
    if count >= MAX_RESTARTS_PER_HOUR:
        log.error(
            "Container %s hit restart limit (%d/%d per hour) — SKIPPING to avoid loop",
            name, count, MAX_RESTARTS_PER_HOUR,
        )
        return

    try:
        log.info("Restarting container %s (attempt %d)...", name, count + 1)
        container.restart(timeout=30)
        restart_counts[name] = count + 1
        restart_reset_time[name] = now
        log.info("Container %s restarted successfully", name)
    except docker.errors.APIError as e:
        log.error("Failed to restart %s: %s — trying compose up", name, e)
        try_compose_up(name)


def try_compose_up(name):
    """Fallback: try to start a stopped container via SDK."""
    try:
        container = client.containers.get(name)
        container.start()
        log.info("Started container %s via SDK", name)
    except docker.errors.NotFound:
        log.error("Container %s not found — manual intervention needed", name)
    except Exception as e:
        log.error("Start fallback for %s failed: %s", name, e)


# ── 2. Disk Pressure Monitor ────────────────────────────────

def check_disk():
    """Monitor disk usage and clean up if thresholds exceeded."""
    log.info("── Disk Pressure Check ──")
    try:
        result = subprocess.run(
            ["df", "--output=pcent", "/"],
            capture_output=True, text=True, timeout=10,
        )
        lines = result.stdout.strip().split("\n")
        pct = int(lines[-1].strip().rstrip("%"))
        log.info("Disk usage: %d%%", pct)

        if pct > DISK_CRITICAL:
            log.warning("Disk CRITICAL (%d%% > %d%%) — running system prune (keep volumes)", pct, DISK_CRITICAL)
            client.containers.prune()
            client.images.prune(filters={"dangling": True})
            client.images.prune()
            client.networks.prune()
            # Never delete named volumes
            log.info("System prune complete (volumes preserved)")
        elif pct > DISK_WARNING:
            log.warning("Disk WARNING (%d%% > %d%%) — pruning images and build cache", pct, DISK_WARNING)
            client.images.prune(filters={"dangling": True})
            try:
                client.api.prune_builds()
            except Exception:
                pass  # Build cache prune may not be available
            log.info("Image/build prune complete")
        else:
            log.info("Disk OK (%d%%)", pct)
    except Exception as e:
        log.error("Disk check failed: %s", e)


# ── 3. Redis Queue Monitor ──────────────────────────────────

def check_queue():
    """Monitor Redis stream length and scale workers accordingly."""
    log.info("── Queue Monitor ──")
    try:
        r = redis.Redis(
            host=REDIS_HOST,
            port=6379,
            db=REDIS_DB,
            password=REDIS_PASSWORD or None,
            socket_timeout=5,
            decode_responses=True,
        )
        stream_len = r.xlen(REDIS_STREAM)
        log.info("Queue '%s' length: %d", REDIS_STREAM, stream_len)

        # Count current workers
        current_workers = count_workers()
        log.info("Current fazle-workers replicas: %d", current_workers)

        if stream_len > QUEUE_SCALE_UP and current_workers < WORKERS_MAX:
            log.warning("Queue backlog (%d > %d) — scaling workers to %d", stream_len, QUEUE_SCALE_UP, WORKERS_MAX)
            scale_workers(WORKERS_MAX)
        elif stream_len < QUEUE_SCALE_DOWN and current_workers > WORKERS_MIN:
            log.info("Queue low (%d < %d) — scaling workers to %d", stream_len, QUEUE_SCALE_DOWN, WORKERS_MIN)
            scale_workers(WORKERS_MIN)
        else:
            log.info("Queue scaling OK (len=%d, workers=%d)", stream_len, current_workers)

    except redis.exceptions.ConnectionError as e:
        log.error("Redis connection failed: %s", e)
    except redis.exceptions.ResponseError as e:
        # Stream may not exist yet
        if "no such key" in str(e).lower():
            log.info("Queue stream '%s' does not exist yet — OK", REDIS_STREAM)
        else:
            log.error("Redis error: %s", e)
    except Exception as e:
        log.error("Queue check failed: %s", e)


def count_workers():
    """Count running fazle-workers containers."""
    containers = client.containers.list(filters={"name": "fazle-workers", "status": "running"})
    return len(containers)


def scale_workers(target):
    """Scale fazle-workers using Docker SDK — clone from existing worker."""
    try:
        current = count_workers()
        if target > current:
            # Scale up: clone from an existing worker
            existing = client.containers.list(filters={"name": "fazle-workers", "status": "running"})
            if not existing:
                log.error("No running fazle-workers to clone from")
                return
            template = existing[0]
            image = template.image
            # Get network names from template
            net_names = list(template.attrs.get("NetworkSettings", {}).get("Networks", {}).keys())
            env = template.attrs.get("Config", {}).get("Env", [])
            for i in range(current + 1, target + 1):
                name = f"fazle-workers-{i}"
                try:
                    # Check if container already exists
                    old = client.containers.get(name)
                    if old.status != "running":
                        old.start()
                        log.info("Started existing %s", name)
                    continue
                except docker.errors.NotFound:
                    pass
                c = client.containers.run(
                    image,
                    detach=True,
                    name=name,
                    environment=env,
                    network=net_names[0] if net_names else None,
                    restart_policy={"Name": "unless-stopped"},
                    labels={"com.docker.compose.project": "fazle-ai", "watchdog.managed": "true"},
                )
                # Attach to additional networks
                for net in net_names[1:]:
                    try:
                        client.networks.get(net).connect(c)
                    except Exception:
                        pass
                log.info("Created and started %s", name)
        elif target < current:
            # Scale down: remove watchdog-managed workers first, then extras
            managed = client.containers.list(filters={"label": "watchdog.managed=true", "name": "fazle-workers"})
            to_remove = sorted(managed, key=lambda c: c.name, reverse=True)
            removed = 0
            for c in to_remove:
                if current - removed <= target:
                    break
                log.info("Stopping scaled worker %s", c.name)
                c.stop(timeout=30)
                c.remove()
                removed += 1
        log.info("Scaled fazle-workers to %d", target)
    except Exception as e:
        log.error("Scale exception: %s", e)


# ── 4. AI Log Analyzer ──────────────────────────────────────

def check_logs():
    """Collect recent logs and analyze with Ollama for crash patterns."""
    log.info("── AI Log Analysis ──")

    all_logs = []
    for cname in LOG_CONTAINERS:
        try:
            container = client.containers.get(cname)
            logs = container.logs(tail=50, timestamps=False).decode("utf-8", errors="replace")
            all_logs.append(f"=== {cname} ===\n{logs}")
        except docker.errors.NotFound:
            log.warning("Container %s not found for log analysis", cname)
        except Exception as e:
            log.error("Failed to get logs from %s: %s", cname, e)

    if not all_logs:
        log.info("No logs collected — skipping analysis")
        return

    combined = "\n".join(all_logs)[-4000:]  # Limit to ~4000 chars for model context

    prompt = (
        "Analyze these Docker container logs. "
        "Report ONLY if you find evidence of: service crashes, repeated errors, "
        "connection refused, tracebacks, or OOM kills. "
        "Reply with a JSON object: {\"status\": \"ok\" or \"alert\", "
        "\"issues\": [\"description\"], \"containers\": [\"affected_name\"]}. "
        "If everything looks normal, reply {\"status\": \"ok\", \"issues\": [], \"containers\": []}.\n\n"
        f"{combined}"
    )

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b"), "prompt": prompt, "stream": False},
            timeout=60,
        )
        if resp.status_code != 200:
            log.error("Ollama returned status %d", resp.status_code)
            return

        response_text = resp.json().get("response", "")
        log.info("Ollama analysis: %s", response_text[:500])

        # Check for critical keywords in the response
        alert_keywords = ["ERROR", "Traceback", "Connection refused", "crash", "OOM", "killed"]
        response_lower = response_text.lower()

        if any(kw.lower() in response_lower for kw in alert_keywords):
            if '"status": "ok"' in response_text or '"status":"ok"' in response_text:
                log.info("Ollama found keywords but status=ok — no action needed")
            else:
                log.warning("Ollama detected potential issue — flagging for review")
                # Don't auto-restart based solely on AI analysis to avoid false positives
                # Log the alert for human review
                log.warning("AI ALERT: %s", response_text[:1000])
        else:
            log.info("AI log analysis: all clear")

    except requests.exceptions.ConnectionError:
        log.warning("Cannot reach Ollama at %s — skipping AI analysis", OLLAMA_URL)
    except requests.exceptions.Timeout:
        log.warning("Ollama request timed out — skipping AI analysis")
    except Exception as e:
        log.error("AI log analysis failed: %s", e)


# ── 5. Prometheus Metric Check ───────────────────────────────

def check_metrics():
    """Query Prometheus for CPU and memory alerts."""
    log.info("── Prometheus Metrics Check ──")
    try:
        # CPU usage per container (rate over 2 minutes)
        cpu_query = 'rate(container_cpu_usage_seconds_total{name!=""}[2m]) * 100'
        resp = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": cpu_query},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                for result in data.get("data", {}).get("result", []):
                    container_name = result.get("metric", {}).get("name", "unknown")
                    cpu_pct = float(result.get("value", [0, 0])[1])
                    if cpu_pct > 90:
                        now = datetime.now()
                        if container_name in CPU_HIGH_SINCE:
                            elapsed = (now - CPU_HIGH_SINCE[container_name]).total_seconds()
                            if elapsed > 120:
                                log.warning(
                                    "HIGH CPU ALERT: %s at %.1f%% for %ds",
                                    container_name, cpu_pct, int(elapsed),
                                )
                        else:
                            CPU_HIGH_SINCE[container_name] = now
                            log.info("CPU elevated for %s: %.1f%%", container_name, cpu_pct)
                    else:
                        CPU_HIGH_SINCE.pop(container_name, None)
            else:
                log.warning("Prometheus query failed: %s", data.get("error", "unknown"))
        else:
            log.warning("Prometheus returned HTTP %d", resp.status_code)

        # Memory check
        mem_query = "node_memory_Active_bytes"
        resp = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": mem_query},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                results = data.get("data", {}).get("result", [])
                if results:
                    mem_bytes = float(results[0].get("value", [0, 0])[1])
                    mem_gb = mem_bytes / (1024**3)
                    log.info("Active memory: %.2f GB", mem_gb)

    except requests.exceptions.ConnectionError:
        log.warning("Cannot reach Prometheus at %s — skipping metrics", PROMETHEUS_URL)
    except Exception as e:
        log.error("Metrics check failed: %s", e)


# ── Main Loop ────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("  AI WATCHDOG — Self-Healing Infrastructure Controller")
    log.info("  Check interval: %ds", CHECK_INTERVAL)
    log.info("  Monitoring %d containers", len(MONITORED))
    log.info("=" * 60)

    cycle = 0
    while not shutdown:
        cycle += 1
        log.info("━━━ Watchdog Cycle #%d ━━━", cycle)
        start = time.time()

        try:
            check_containers()
        except Exception as e:
            log.error("Container check crashed: %s", e)

        try:
            check_disk()
        except Exception as e:
            log.error("Disk check crashed: %s", e)

        try:
            check_queue()
        except Exception as e:
            log.error("Queue check crashed: %s", e)

        # AI log analysis every 5th cycle (~2.5 min) to reduce Ollama load
        if cycle % 5 == 1:
            try:
                check_logs()
            except Exception as e:
                log.error("Log analysis crashed: %s", e)

        # Metrics every 2nd cycle (~1 min)
        if cycle % 2 == 0:
            try:
                check_metrics()
            except Exception as e:
                log.error("Metrics check crashed: %s", e)

        elapsed = time.time() - start
        log.info("Cycle #%d complete in %.1fs", cycle, elapsed)

        # Sleep in small increments for responsive shutdown
        remaining = max(0, CHECK_INTERVAL - elapsed)
        while remaining > 0 and not shutdown:
            time.sleep(min(remaining, 1))
            remaining -= 1

    log.info("Watchdog shutdown complete.")


if __name__ == "__main__":
    main()
