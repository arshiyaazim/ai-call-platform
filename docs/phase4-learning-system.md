# Phase 4: Autonomous AI Learning System — Migration Notes

## Overview

Phase 4 adds two new services and updates two existing services to transform Fazle AI into a self-improving personal digital clone with centralized LLM routing, autonomous learning, relationship tracking, and user correction processing.

---

## New Services

### 1. fazle-llm-gateway (Port 8800)

**Purpose**: Centralized LLM routing with caching, streaming, rate limiting, model fallback, and usage tracking.

**Directory**: `fazle-system/llm-gateway/`

**Endpoints**:
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/generate` | POST | Unified LLM generation (with cache, fallback, rate limit) |
| `/embeddings` | POST | OpenAI embedding proxy |
| `/usage` | GET | Usage stats per caller per day |
| `/health` | GET | Health check |
| `/metrics` | GET | Prometheus metrics |

**Key Features**:
- **Response caching**: Redis-backed, key `llm_cache:{sha256(prompt+model)}`, configurable TTL (default 300s)
- **Model fallback**: If primary provider fails, falls back to `FALLBACK_PROVIDER/FALLBACK_MODEL`
- **Rate limiting**: Sliding window per caller, configurable RPM (default 60)
- **Streaming**: SSE streaming for both OpenAI and Ollama
- **Usage tracking**: Per-caller daily token counting in Redis (7-day retention)
- **Context injection**: Optional extra context prepended to system prompt

**New Environment Variables**:
| Variable | Default | Description |
|----------|---------|-------------|
| `FALLBACK_PROVIDER` | `ollama` | Fallback LLM provider |
| `FALLBACK_MODEL` | `llama3.1` | Fallback model name |
| `CACHE_TTL` | `300` | Response cache TTL in seconds (0=disabled) |
| `RATE_LIMIT_RPM` | `60` | Max requests per minute per caller |

**Redis DB**: 3 (new)

---

### 2. fazle-learning-engine (Port 8900)

**Purpose**: Autonomous self-improvement via conversation analysis, relationship graph, user corrections, and nightly learning runs.

**Directory**: `fazle-system/learning-engine/`

**Endpoints**:
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/learn` | POST | Analyze conversation, extract knowledge/relationships/corrections |
| `/nightly-learn` | POST | Batch process last 24h of conversations |
| `/corrections` | POST | Record a user correction |
| `/corrections` | GET | List corrections (filterable by applied status) |
| `/relationships` | POST | Upsert a person in the relationship graph |
| `/relationships` | GET | List all relationships |
| `/relationships/{name}` | GET | Get specific person |
| `/runs` | GET | List learning run history |
| `/stats` | GET | Aggregate learning statistics |
| `/health` | GET | Health check |
| `/metrics` | GET | Prometheus metrics |

**New PostgreSQL Tables** (auto-created on startup):
| Table | Purpose |
|-------|---------|
| `fazle_relationship_graph` | Person name, relationship type, attributes, interaction count |
| `fazle_corrections` | Original/corrected responses, user feedback, applied status |
| `fazle_learning_runs` | Learning run history with counts and summaries |

**Redis DB**: 4 (new)

---

## Modified Services

### fazle-brain (Port 8200 — unchanged)

**Changes**:
- Added `query_gateway()` function that calls LLM Gateway instead of Ollama/OpenAI directly
- `query_llm()` now routes through gateway first, falls back to direct provider if gateway is unavailable
- After each `/chat` response, triggers async learning via `POST /learn` on the learning engine
- **New env vars**: `LLM_GATEWAY_URL`, `LEARNING_ENGINE_URL`, `USE_LLM_GATEWAY`
- **Backward compatible**: Set `USE_LLM_GATEWAY=false` to revert to direct LLM calls

### fazle-trainer (Port 8600 — unchanged)

**Changes**:
- `query_llm()` now routes through gateway first, falls back to direct provider if gateway is unavailable
- **New env vars**: `LLM_GATEWAY_URL`, `USE_LLM_GATEWAY`
- **Backward compatible**: Set `USE_LLM_GATEWAY=false` to revert to direct LLM calls

---

## Deployment Steps

### Pre-deployment
1. No new secrets required — gateway uses existing `OPENAI_API_KEY` and `REDIS_PASSWORD`
2. No manual database migration — tables are created automatically on startup
3. No nginx changes needed — new services are internal-only (no external ports)

### Deployment Order
```bash
cd /home/azim/ai-call-platform/fazle-ai

# 1. Build new services first
docker compose -f fazle-docker-compose.yaml build fazle-llm-gateway fazle-learning-engine

# 2. Start new services
docker compose -f fazle-docker-compose.yaml up -d fazle-llm-gateway
docker compose -f fazle-docker-compose.yaml up -d fazle-learning-engine

# 3. Verify new services are healthy
docker compose -f fazle-docker-compose.yaml ps fazle-llm-gateway fazle-learning-engine

# 4. Rebuild and restart brain (picks up gateway routing)
docker compose -f fazle-docker-compose.yaml build fazle-brain
docker compose -f fazle-docker-compose.yaml up -d fazle-brain

# 5. Rebuild and restart trainer
docker compose -f fazle-docker-compose.yaml build fazle-trainer
docker compose -f fazle-docker-compose.yaml up -d fazle-trainer

# 6. Verify everything
docker compose -f fazle-docker-compose.yaml ps
curl -s http://localhost:8800/health | jq .
curl -s http://localhost:8900/health | jq .
```

### Rollback
Set `USE_LLM_GATEWAY=false` in brain/trainer env vars and restart — they'll fall back to direct LLM calls immediately.

---

## Architecture

```
                          ┌──────────────────┐
                          │  fazle-brain     │
                          │  :8200           │
                          └────────┬─────────┘
                                   │
                     ┌─────────────┼─────────────┐
                     │             │              │
              ┌──────▼──────┐ ┌───▼───┐  ┌───────▼────────┐
              │ llm-gateway │ │memory │  │learning-engine │
              │ :8800       │ │:8300  │  │ :8900          │
              └──────┬──────┘ └───────┘  └───────┬────────┘
                     │                           │
            ┌────────┼────────┐          ┌───────┼───────┐
            │        │        │          │       │       │
        ┌───▼──┐ ┌───▼────┐ ┌▼────┐ ┌───▼──┐ ┌─▼────┐ ┌▼────────┐
        │Ollama│ │OpenAI  │ │Redis│ │Postgres│ │Memory│ │LLM GW   │
        └──────┘ └────────┘ │DB 3 │ │       │ │:8300 │ │:8800    │
                            └─────┘ └───────┘ └──────┘ └─────────┘
```

---

## Container Compatibility

| Item | Status |
|------|--------|
| Container names | ✅ Unchanged (brain, trainer, memory, etc.) |
| Ports | ✅ Unchanged (8100-8700, 3020) |
| Hostnames | ✅ Unchanged |
| Env var names | ✅ Unchanged (new ones added, none removed) |
| Nginx routing | ✅ No changes needed |
| Docker volumes | ✅ No changes needed |
| Networks | ✅ Same external networks (app-network, ai-network, db-network) |
| Rolling deploy labels | ✅ Preserved on all existing services |

---

## Redis DB Allocation

| DB | Service | Purpose |
|----|---------|---------|
| 0 | (default) | Unused |
| 1 | fazle-brain | Conversation history (TTL 24h) |
| 2 | fazle-trainer | Training sessions (TTL 30d) |
| 3 | fazle-llm-gateway | Response cache + rate limits + usage stats |
| 4 | fazle-learning-engine | General state |

---

## Files Created

| File | Description |
|------|-------------|
| `fazle-system/llm-gateway/main.py` | LLM Gateway FastAPI service |
| `fazle-system/llm-gateway/Dockerfile` | Docker build file |
| `fazle-system/llm-gateway/requirements.txt` | Python dependencies |
| `fazle-system/learning-engine/main.py` | Learning Engine FastAPI service |
| `fazle-system/learning-engine/Dockerfile` | Docker build file |
| `fazle-system/learning-engine/requirements.txt` | Python dependencies |
| `tests/test_llm_gateway.py` | Gateway unit tests |
| `tests/test_learning_engine.py` | Learning engine unit tests |

## Files Modified

| File | Changes |
|------|---------|
| `fazle-system/brain/main.py` | Added gateway routing + learning trigger |
| `fazle-system/trainer/main.py` | Added gateway routing |
| `fazle-ai/fazle-docker-compose.yaml` | Added 2 new services + env vars |
