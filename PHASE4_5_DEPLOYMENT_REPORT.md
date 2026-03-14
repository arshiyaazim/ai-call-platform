# Phase 4 & 5 Production Deployment Report

**Date:** 2026-03-13  
**VPS:** Contabo `5.189.131.48` (user: `azim`)  
**Deployer:** Automated via SSH from local workstation  
**Status:** ✅ COMPLETE — All services healthy, load test passed

---

## Deployment Summary

### Phase 4 — LLM Gateway & Learning Engine
| Service | Port | Purpose |
|---|---|---|
| `fazle-llm-gateway` | 8800 | Centralized LLM routing with caching, model fallback, rate limiting, batching, Prometheus metrics |
| `fazle-learning-engine` | 8900 | Autonomous self-improvement — conversation analysis, relationship graph, user corrections, nightly learning |

### Phase 5 — Async Queue & Workers
| Service | Port | Purpose |
|---|---|---|
| `fazle-queue` | 8810 | Redis Streams-based async request queue (Redis DB 5) |
| `fazle-workers` | 8820 | Consumer pool with horizontal scaling (2 replicas) |

### Modified Services
| Service | Changes |
|---|---|
| `fazle-brain` | Routes through LLM Gateway (`USE_LLM_GATEWAY=true`), reports to Learning Engine |
| `fazle-trainer` | Routes through LLM Gateway (`USE_LLM_GATEWAY=true`) |
| `ollama` | Concurrency protection: `NUM_PARALLEL=1`, `MAX_LOADED_MODELS=1`, `MAX_QUEUE=2` |

---

## Resource Protections Applied

| Resource | Limit | Rationale |
|---|---|---|
| **Workers** | 2 replicas (NOT 4) | 7.8GB RAM constraint |
| **Ollama concurrency** | 1 parallel | Prevent RAM exhaustion |
| **Ollama max queue** | 2 | Prevent request pile-up |
| **LLM batch size** | 4 max | Balance throughput vs latency |
| **Batch window** | 75ms | Low-latency batching |
| **Rate limit** | 10 req/s per user | Prevent abuse |

### Container Resource Limits
| Service | CPU | Memory (limit) | Memory (reservation) |
|---|---|---|---|
| fazle-llm-gateway | 1 core | 1GB | 256MB |
| fazle-learning-engine | 0.5 cores | 512MB | 128MB |
| fazle-queue | 0.5 cores | 512MB | 128MB |
| fazle-workers (×2) | 1 core each | 1GB each | 256MB each |

---

## Network Configuration

| Service | Networks |
|---|---|
| fazle-llm-gateway | `ai-network`, `app-network`, `db-network` |
| fazle-learning-engine | `ai-network`, `db-network` |
| fazle-queue | `ai-network`, `db-network` |
| fazle-workers | `ai-network`, `db-network` |

**Note:** Gateway requires `db-network` for Redis access (caching, rate limiting, usage tracking on DB 3).

---

## Redis Database Allocation

| DB | Service |
|---|---|
| 0 | Default |
| 1 | fazle-brain |
| 2 | fazle-trainer |
| 3 | fazle-llm-gateway |
| 4 | fazle-learning-engine |
| 5 | fazle-queue & fazle-workers |

---

## LLM Configuration

| Setting | Value |
|---|---|
| Primary provider | OpenAI (gpt-4o) |
| Fallback provider | Ollama (qwen2.5:3b) |
| Installed Ollama model | qwen2.5:3b (1.9GB, 3.1B params) |
| Cache TTL | 300s |

---

## Load Test Results (20 users × 2 rounds)

| Phase | Requests | Success | Errors | Rate-Limited | Cache Hits | Avg Latency |
|---|---|---|---|---|---|---|
| Sync Gateway | 40 | 40 (100%) | 0 | 0 | 38 | 332ms (p50: 94ms) |
| Async Queue | 40 | 40 (100%) | 0 | 0 | 40 | 668ms |
| Rate Limit Burst | 30 | 10 | 0 | 20 ✓ | 10 | 114ms |
| Cache Test | 20 | 10 | 0 | 10 ✓ | 10 | 6ms |

All features verified: caching, rate limiting, async queue processing, model fallback.

---

## System Health Post-Deployment

| Metric | Value | Status |
|---|---|---|
| Total containers | 29 (was 25) | All healthy |
| RAM usage | 5.8GB / 7.8GB | 1.7GB available |
| Swap | 992MB / 3GB | Normal |
| Load average | 4.08 (4 CPUs) | At capacity |
| Disk | 61GB / 73GB (83%) | Monitor |

### New Service Resource Usage
| Service | Memory | CPU |
|---|---|---|
| fazle-llm-gateway | 57MB | 0.25% |
| fazle-workers (×2) | ~57MB each | <0.5% |
| fazle-queue | ~50MB | <0.1% |
| fazle-learning-engine | ~45MB | <0.1% |

---

## Issues Encountered & Resolved

### 1. Gateway Redis Connectivity (Critical)
- **Symptom:** All gateway requests returning 502, Redis DNS resolution failure
- **Root cause:** `fazle-llm-gateway` was not connected to `db-network` where Redis lives
- **Fix:** Added `db-network` to gateway's networks in docker-compose.yaml
- **Verified:** Gateway health shows "healthy", load test 100% pass

### 2. Ollama Model Mismatch
- **Symptom:** Fallback to Ollama returned 404 Not Found
- **Root cause:** FALLBACK_MODEL defaulted to `llama3.1` but only `qwen2.5:3b` is installed
- **Fix:** Updated OLLAMA_MODEL and FALLBACK_MODEL defaults to `qwen2.5:3b`

### 3. Container Name Conflicts
- **Symptom:** Brain/trainer recreation failed due to existing containers
- **Fix:** `docker stop && docker rm` before `docker compose up -d --no-deps`

---

## Backup Location

```
/home/azim/backups/pre-phase5/
├── docker-compose.yaml.bak    (27KB — original monolithic compose)
└── db-dump.sql.gz             (11KB — PostgreSQL dump)
```

## Rollback Procedure

```bash
cd /home/azim/ai-call-platform
# Restore original compose
cp /home/azim/backups/pre-phase5/docker-compose.yaml.bak docker-compose.yaml
# Remove new services
docker compose rm -sf fazle-llm-gateway fazle-learning-engine fazle-queue fazle-workers
# Restart brain/trainer without gateway routing
docker compose up -d --no-deps fazle-brain fazle-trainer
# Restore Ollama settings
docker compose up -d --no-deps ollama
# Restore DB if needed
gunzip -c /home/azim/backups/pre-phase5/db-dump.sql.gz | docker exec -i ai-postgres psql -U postgres
```

---

## Architecture (Post Phase 4+5)

```
                    ┌──────────────┐
                    │   Clients    │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │    Nginx     │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
      ┌───────▼──┐  ┌──────▼───┐  ┌────▼─────┐
      │ fazle-api │  │ fazle-ui │  │ dograh   │
      └───────┬──┘  └──────────┘  └──────────┘
              │
      ┌───────▼──────────┐
      │   fazle-brain    │──── USE_LLM_GATEWAY=true
      └───────┬──────────┘
              │
    ┌─────────▼──────────┐     ┌─────────────────────┐
    │ fazle-llm-gateway  │◄───►│  Redis (DB 3)       │
    │  (rate limit,cache,│     │  cache, rate limits  │
    │   batch, fallback) │     └─────────────────────┘
    └────────┬───────────┘
             │
    ┌────────┼────────┐
    │                 │
┌───▼────┐     ┌─────▼───────┐
│ OpenAI │     │   Ollama    │
│ gpt-4o │     │ qwen2.5:3b  │
└────────┘     └─────────────┘

    ┌─────────────────┐     ┌──────────────┐
    │   fazle-queue   │────►│ Redis (DB 5) │
    │  (async submit) │     │ Streams      │
    └─────────────────┘     └──────┬───────┘
                                   │
                        ┌──────────▼──────────┐
                        │   fazle-workers     │
                        │   (2 replicas)      │
                        └─────────────────────┘

    ┌─────────────────────┐     ┌──────────────┐
    │ fazle-learning-engine│────►│ Redis (DB 4) │
    │ (self-improvement)  │     └──────────────┘
    └─────────────────────┘
```
