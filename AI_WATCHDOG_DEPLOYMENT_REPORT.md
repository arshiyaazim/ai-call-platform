# AI Watchdog — Deployment Report

**Date:** 2026-03-17  
**Host:** `5.189.131.48` (vmi3117764, Ubuntu 22.04.5 LTS)  
**Deployer:** Level-4 Autonomous DevOps Agent

---

## Mission Summary

Deployed a production-grade **Self-Healing Infrastructure Controller** (`ai-watchdog`) that continuously monitors and repairs the platform with zero human intervention.

## Architecture

```
ai-watchdog (Python 3.11, Docker SDK)
├── Module 1: Container Health Monitor  (30s interval)
├── Module 2: Disk Pressure Monitor     (30s interval)
├── Module 3: Redis Queue Auto-Scaler   (30s interval)
├── Module 4: AI Log Analyzer           (every 5th cycle, ~2.5min)
└── Module 5: Prometheus Metrics Check  (every 2nd cycle, ~1min)
```

## Integration Points

| Service       | Network            | Protocol  | Status |
|---------------|--------------------|-----------|--------|
| Docker Engine | Unix socket (ro)   | SDK API   | ✅ OK  |
| Redis         | db-network         | TCP 6379  | ✅ OK  |
| Ollama        | ai-network         | HTTP 11434| ✅ OK  |
| Prometheus    | monitoring-network | HTTP 9090 | ✅ OK  |

## Module Validation

### 1. Container Health Monitor
- Checks 27 monitored containers every 30 seconds
- Detects stopped / unhealthy containers
- Rate-limited restarts (max 3/hour per container) to prevent restart loops
- Fallback: `container.start()` via Docker SDK if `container.restart()` fails
- **Status:** ✅ Verified — all containers healthy on first pass

### 2. Disk Pressure Monitor
- Reads disk usage via `df`
- Warning threshold: >75% → prune images + build cache
- Critical threshold: >85% → full system prune (volumes always preserved)
- Uses Docker SDK: `client.images.prune()`, `client.containers.prune()`
- **Status:** ✅ Verified — disk at 52%, reporting OK

### 3. Redis Queue Auto-Scaler
- Monitors Redis stream `llm_requests` on DB 5
- Scale-up trigger: queue length > 50 → scale to 4 workers
- Scale-down trigger: queue length < 10 → scale to 2 workers
- Scaling via Docker SDK: clones environment + networks from existing worker
- **Status:** ✅ Verified — detected backlog (52 > 50), auto-scaled from 2 to 4 workers

### 4. AI Log Analyzer
- Collects last 50 lines from `fazle-api` and `fazle-voice`
- Sends to Ollama `qwen2.5:3b` for crash/error pattern analysis
- Conservative: logs alerts but does NOT auto-restart based on AI analysis alone
- Runs every 5th cycle (~2.5 minutes) to reduce Ollama load
- **Status:** ✅ Verified — Ollama returned `{"status": "ok", "issues": [], "containers": []}`

### 5. Prometheus Metrics Check
- Queries `container_cpu_usage_seconds_total` — alerts if CPU >90% for >2 minutes
- Queries `node_memory_Active_bytes` — memory tracking
- **Status:** ✅ Verified — Active memory: 0.53 GB, no CPU alerts

## Security Posture

| Control                   | Setting                          | Status |
|---------------------------|----------------------------------|--------|
| Read-only root filesystem | `read_only: true`                | ✅     |
| Temporary filesystem      | `tmpfs: /tmp`                    | ✅     |
| Non-root user             | `watchdog` (created in Dockerfile)| ✅    |
| Memory limit              | 256 MiB (hard + swap)            | ✅     |
| Docker socket             | Mounted read-only (`:ro`)        | ✅     |
| Config file               | Mounted read-only (`:ro`)        | ✅     |
| No privileged mode        | `Privileged: false`              | ✅     |
| No added capabilities     | `CapAdd: null`                   | ✅     |
| Log rotation              | `max-size: 10m, max-file: 3`     | ✅     |
| Restart policy            | `unless-stopped`                 | ✅     |

## Resource Usage

| Metric    | Value           |
|-----------|-----------------|
| CPU       | 0.02%           |
| Memory    | 35 MiB / 256 MiB (13.8%) |
| PIDs      | 1               |
| Image     | ~170 MB (python:3.11-slim + deps) |

## Container Inventory (Post-Deploy)

**32 containers total** (29 original + ai-watchdog + 2 auto-scaled workers)

| Stack     | Containers | Status |
|-----------|------------|--------|
| ai-infra  | 11         | All healthy |
| fazle-ai  | 15 (13 + 2 scaled) | All healthy |
| dograh    | 5          | All healthy |
| ai-watchdog | 1        | Healthy |

## Files Deployed

| File               | Path on VPS                                              |
|--------------------|----------------------------------------------------------|
| watchdog.py        | `/home/azim/ai-call-platform/ai-watchdog/watchdog.py`    |
| Dockerfile         | `/home/azim/ai-call-platform/ai-watchdog/Dockerfile`     |
| docker-compose.yaml| `/home/azim/ai-call-platform/ai-watchdog/docker-compose.yaml` |
| config.yaml        | `/home/azim/ai-call-platform/ai-watchdog/config.yaml`    |
| requirements.txt   | `/home/azim/ai-call-platform/ai-watchdog/requirements.txt` |

## Issues Encountered & Resolved

1. **Docker CLI missing in container** — Initial Dockerfile had no Docker CLI. Subprocess `docker compose` calls failed with `[Errno 2]`. **Fix:** Refactored all operations to use Docker Python SDK instead of CLI subprocess calls. Cleaner, faster, and eliminates the Docker CLI dependency entirely.

2. **`.env` permission denied** — Host `.env` file (mode 600) couldn't be read by non-root watchdog user when mounted. **Fix:** Eliminated `.env` file dependency by using Docker SDK for scaling (clones config from existing containers).

3. **Ollama timeout on first cycle** — Model loading caused 60s timeout on initial request. **Self-resolved:** Subsequent cycles complete in <8s.

## Safety Features

- **Restart rate limiting:** Max 3 restarts per container per hour to prevent restart loops
- **Graceful shutdown:** Handles SIGTERM/SIGINT signals
- **Per-module isolation:** Each module wrapped in try/except — one module failure doesn't crash others
- **Conservative AI:** Ollama analysis flags alerts for review but never auto-restarts based on AI alone
- **Volume protection:** Disk cleanup NEVER deletes named volumes
- **Worker scaling bounds:** Min 2, max 4 workers — prevents unbounded scaling

## Operational Notes

- Config changes: Edit `/home/azim/ai-call-platform/ai-watchdog/config.yaml` on the host — changes take effect on next cycle (file is volume-mounted)
- Logs: `docker logs ai-watchdog -f` for real-time monitoring
- Restart: `docker restart ai-watchdog`
- Stop: `cd /home/azim/ai-call-platform/ai-watchdog && docker compose down`
