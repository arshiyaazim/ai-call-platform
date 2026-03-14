# Phase 5 — Scalability Upgrade: 10× Concurrent Users

## Overview

This upgrade adds an **async request queue**, **worker pool**, **request batching**, **enhanced rate limiting**, and **Prometheus metrics** to the Fazle AI system, enabling 10× more concurrent users on the same VPS hardware.

## New Services

### fazle-queue (Port 8810)
**Redis Streams-based async request queue.**

- **Redis DB 5** — dedicated stream storage
- Stream name: `llm_requests`, consumer group: `llm_workers`
- Task lifecycle: `pending → processing → completed | failed`
- Results stored in Redis hashes (`task:{uuid}`) with configurable TTL (default 600s)
- Stream capped at 10,000 entries (FIFO eviction)

**Endpoints:**
| Method | Path | Description |
|--------|------|-------------|
| POST | `/enqueue` | Submit LLM request, get task_id |
| GET | `/status/{task_id}` | Poll for task result |
| GET | `/queue/info` | Stream stats, consumer groups, pending counts |
| POST | `/task/{task_id}/complete` | Internal: workers report success |
| POST | `/task/{task_id}/fail` | Internal: workers report failure |
| GET | `/health` | Health check |
| GET | `/metrics` | Prometheus metrics |

**Prometheus Metrics:**
- `fazle_queue_length` (gauge) — pending messages in stream
- `fazle_tasks_enqueued_total` (counter) — total tasks submitted
- `fazle_tasks_completed_total` (counter) — total tasks completed
- `fazle_tasks_failed_total` (counter) — total tasks failed

### fazle-workers (Port 8820, 4 replicas)
**Horizontally scalable worker pool consuming from the queue.**

- Uses Redis Streams consumer groups (`XREADGROUP`) for reliable delivery
- Each worker reads up to 5 messages per batch
- Calls LLM Gateway `/generate` for inference
- Reports results back to fazle-queue
- Auto-claims stale messages from crashed workers (60s idle threshold)
- Retries failed tasks up to 3 times

**Endpoints:**
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (Redis + consumer loop) |
| GET | `/worker/stats` | Stream length, pending count |
| GET | `/metrics` | Prometheus metrics |

**Prometheus Metrics:**
- `fazle_worker_tasks_processed_total{status}` (counter) — tasks by outcome
- `fazle_worker_llm_latency_seconds` (histogram) — LLM call latency
- `fazle_worker_active_tasks` (gauge) — currently processing
- `fazle_worker_idle` (gauge) — 1 if idle

## LLM Gateway Enhancements (v2.0.0)

### Request Batching
- Collects requests within a **75ms window** (configurable via `BATCH_WINDOW_MS`)
- Dispatches up to **8 requests** concurrently when window fills or timer fires
- Reduces overhead from sequential processing
- Streaming requests bypass batching (direct dispatch)

### Per-User Rate Limiting
- **New:** 10 requests/second per end-user (sliding window, 1s granularity)
- **Existing:** 60 requests/minute per caller service (unchanged)
- Controlled via `RATE_LIMIT_PER_USER_RPS` env var
- New `user_id` field on `/generate` request body

### Enhanced Prometheus Metrics
| Metric | Type | Description |
|--------|------|-------------|
| `llm_cache_hits_total` | counter | Cache hit count |
| `llm_cache_misses_total` | counter | Cache miss count |
| `llm_request_latency_seconds{provider}` | histogram | LLM call latency by provider |
| `llm_requests_total{provider,status}` | counter | Requests by provider and outcome |
| `llm_rate_limited_total{limiter}` | counter | Rate-limited requests by limiter type |

## Docker Compose Changes

### New Services Added
```yaml
fazle-queue:
  container_name: fazle-queue
  networks: ai-network, db-network
  resources: 0.5 CPU, 256M RAM
  depends_on: fazle-llm-gateway (healthy)

fazle-workers:
  container_name: fazle-workers
  replicas: 4
  networks: ai-network, db-network
  resources: 0.5 CPU × 4, 256M RAM × 4
  depends_on: fazle-queue (healthy), fazle-llm-gateway (healthy)
```

### New Environment Variables
| Variable | Default | Service | Description |
|----------|---------|---------|-------------|
| `FAZLE_RATE_LIMIT_PER_USER_RPS` | 10 | llm-gateway | Per-user requests/second |
| `FAZLE_BATCH_WINDOW_MS` | 75 | llm-gateway | Batch collection window (ms) |
| `FAZLE_BATCH_MAX_SIZE` | 8 | llm-gateway | Max requests per batch |

### Redis DB Allocation
| DB | Service |
|----|---------|
| 1 | fazle-brain |
| 2 | fazle-trainer |
| 3 | fazle-llm-gateway |
| 4 | fazle-learning-engine |
| **5** | **fazle-queue + fazle-workers** (NEW) |

## Resource Budget

| Service | CPU | RAM | Count | Total CPU | Total RAM |
|---------|-----|-----|-------|-----------|-----------|
| fazle-queue | 0.5 | 256M | 1 | 0.5 | 256M |
| fazle-workers | 0.5 | 256M | 4 | 2.0 | 1024M |
| **Total new** | | | 5 | **2.5** | **1280M** |

## Preserved (No Changes)
- ✅ Container names, ports, existing nginx routing
- ✅ Database schemas, Docker volumes
- ✅ All existing service definitions
- ✅ Network topology (app-network, db-network, ai-network)

## Load Testing

```bash
# From the VPS or locally with port forwarding:
python scripts/load-test.py \
  --gateway http://localhost:8800 \
  --queue http://localhost:8810 \
  --users 50 \
  --rounds 3
```

The load test runs 4 phases:
1. **Sync gateway** — 50 users × 3 rounds hitting `/generate` directly
2. **Async queue** — 50 users × 3 rounds via `/enqueue` + polling
3. **Rate limit burst** — 30 requests from one user in 1 second
4. **Cache test** — same prompt 20 times to measure hit rate

## Deployment

```bash
cd fazle-ai
docker compose -f fazle-docker-compose.yaml --env-file ../.env build fazle-queue fazle-workers fazle-llm-gateway
docker compose -f fazle-docker-compose.yaml --env-file ../.env up -d fazle-queue fazle-workers
docker compose -f fazle-docker-compose.yaml --env-file ../.env up -d fazle-llm-gateway  # restart for batching
```

## Architecture Flow

```
Client → fazle-api → fazle-brain → fazle-llm-gateway (sync path)
                                      ↓ batching window
                                    Provider (OpenAI / Ollama)

Client → fazle-api → fazle-queue → Redis Stream → fazle-workers (×4)
                        ↑ poll                        ↓
                     status/{id}              fazle-llm-gateway
                                                   ↓
                                              Provider (OpenAI / Ollama)
```
