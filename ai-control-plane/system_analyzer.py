#!/usr/bin/env python3
"""
System Analyzer — Collects comprehensive system snapshot.
Gathers container health, CPU, memory, disk, Redis queue, and Prometheus metrics.
"""

import os
import logging
import subprocess
from datetime import datetime

import docker
import psutil
import redis
import requests

log = logging.getLogger("control-plane.analyzer")

client = docker.from_env()

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
REDIS_HOST = os.getenv("REDIS_HOST", "ai-redis")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")


def collect_snapshot(config: dict) -> dict:
    """Collect full system snapshot."""
    snapshot = {
        "timestamp": datetime.utcnow().isoformat(),
        "containers": _collect_containers(config),
        "system": _collect_system_resources(),
        "disk": _collect_disk(),
        "queue": _collect_queue(config),
        "prometheus": _collect_prometheus(),
    }
    return snapshot


def _collect_containers(config: dict) -> list:
    """Get status of all monitored containers."""
    monitored = config.get("monitored_containers", [])
    all_containers = {c.name: c for c in client.containers.list(all=True)}
    result = []

    for name in monitored:
        c = all_containers.get(name)
        if c is None:
            result.append({"name": name, "status": "not_found", "health": "unknown"})
            continue

        health = c.attrs.get("State", {}).get("Health", {})
        health_status = health.get("Status", "none")

        # Get recent logs for unhealthy containers
        recent_logs = ""
        if c.status != "running" or health_status == "unhealthy":
            try:
                recent_logs = c.logs(tail=20, timestamps=False).decode("utf-8", errors="replace")[-1000:]
            except Exception:
                pass

        result.append({
            "name": name,
            "status": c.status,
            "health": health_status,
            "recent_logs": recent_logs if recent_logs else None,
        })

    return result


def _collect_system_resources() -> dict:
    """Collect CPU and memory from host perspective."""
    try:
        cpu_pct = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        return {
            "cpu_percent": cpu_pct,
            "memory_total_gb": round(mem.total / (1024 ** 3), 2),
            "memory_used_gb": round(mem.used / (1024 ** 3), 2),
            "memory_percent": mem.percent,
        }
    except Exception as e:
        log.error("System resource collection failed: %s", e)
        return {"cpu_percent": 0, "memory_total_gb": 0, "memory_used_gb": 0, "memory_percent": 0}


def _collect_disk() -> dict:
    """Collect disk usage."""
    try:
        result = subprocess.run(
            ["df", "--output=pcent,avail", "/"],
            capture_output=True, text=True, timeout=10,
        )
        lines = result.stdout.strip().split("\n")
        parts = lines[-1].strip().split()
        pct = int(parts[0].rstrip("%"))
        avail_kb = int(parts[1])
        return {
            "usage_percent": pct,
            "available_gb": round(avail_kb / (1024 * 1024), 2),
        }
    except Exception as e:
        log.error("Disk collection failed: %s", e)
        return {"usage_percent": 0, "available_gb": 0}


def _collect_queue(config: dict) -> dict:
    """Check Redis queue length and worker count."""
    redis_db = config.get("redis_db", 5)
    redis_stream = config.get("redis_stream", "llm_requests")
    try:
        r = redis.Redis(
            host=REDIS_HOST,
            port=6379,
            db=redis_db,
            password=REDIS_PASSWORD or None,
            socket_timeout=5,
            decode_responses=True,
        )
        stream_len = r.xlen(redis_stream)
        workers = len(client.containers.list(filters={"name": "fazle-workers", "status": "running"}))
        return {
            "stream": redis_stream,
            "length": stream_len,
            "workers_running": workers,
        }
    except redis.exceptions.ConnectionError:
        log.warning("Redis connection failed")
        return {"stream": redis_stream, "length": -1, "workers_running": 0}
    except redis.exceptions.ResponseError as e:
        if "no such key" in str(e).lower():
            workers = len(client.containers.list(filters={"name": "fazle-workers", "status": "running"}))
            return {"stream": redis_stream, "length": 0, "workers_running": workers}
        log.error("Redis error: %s", e)
        return {"stream": redis_stream, "length": -1, "workers_running": 0}
    except Exception as e:
        log.error("Queue collection failed: %s", e)
        return {"stream": redis_stream, "length": -1, "workers_running": 0}


def _collect_prometheus() -> dict:
    """Collect key Prometheus metrics."""
    metrics = {}
    try:
        # Container CPU rate
        resp = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": 'sum(rate(container_cpu_usage_seconds_total{name!=""}[2m])) by (name) * 100'},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                high_cpu = []
                for r in data.get("data", {}).get("result", []):
                    name = r.get("metric", {}).get("name", "")
                    val = float(r.get("value", [0, 0])[1])
                    if val > 50:
                        high_cpu.append({"name": name, "cpu_percent": round(val, 1)})
                metrics["high_cpu_containers"] = high_cpu

        # Node memory
        resp = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": "node_memory_Active_bytes"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                results = data.get("data", {}).get("result", [])
                if results:
                    mem_gb = float(results[0].get("value", [0, 0])[1]) / (1024 ** 3)
                    metrics["active_memory_gb"] = round(mem_gb, 2)

    except requests.exceptions.ConnectionError:
        log.warning("Cannot reach Prometheus")
    except Exception as e:
        log.error("Prometheus collection failed: %s", e)

    return metrics
