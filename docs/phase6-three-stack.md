# Phase 6 — Three-Stack Production Layout

## Overview

Phase 6 splits the monolithic `docker-compose.yaml` into three independent stacks with shared external Docker networks. Each stack can be deployed, restarted, and scaled independently.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   External Networks                      │
│  app-network │ db-network │ ai-network │ monitoring-net │
└──────┬───────┴─────┬──────┴─────┬──────┴───────┬────────┘
       │             │            │              │
┌──────┴─────────────┴────────────┴──────────────┴────────┐
│  ai-infra/docker-compose.yaml  (Deploy Order: 1)        │
│  postgres, redis, minio, qdrant, ollama                  │
│  livekit, coturn, cloudflared                            │
│  prometheus, grafana, node-exporter, cadvisor, loki,     │
│  promtail                                                │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│  dograh/docker-compose.yaml  (Deploy Order: 2)          │
│  dograh-api, dograh-ui                                   │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│  fazle-ai/docker-compose.yaml  (Deploy Order: 3)        │
│  fazle-api, fazle-brain, fazle-memory, fazle-task-engine │
│  fazle-web-intelligence, fazle-trainer, fazle-voice      │
│  fazle-ui, fazle-llm-gateway, fazle-learning-engine      │
│  fazle-queue, fazle-workers (×2 replicas)                │
└─────────────────────────────────────────────────────────┘
```

## Network Layout

| Network | Type | Purpose |
|---------|------|---------|
| `app-network` | bridge | HTTP routing, Nginx proxy, cross-stack communication |
| `db-network` | internal | Database access (Postgres, Redis, MinIO, Qdrant) |
| `ai-network` | internal | LLM services (Ollama), inter-Fazle RPC |
| `monitoring-network` | internal | Prometheus scraping, Loki log shipping |

All networks are **external** — pre-created by `scripts/create-networks.sh`.

## Deployment

### First-time setup

```bash
# 1. Create shared networks
./scripts/create-networks.sh

# 2. Start all stacks in order
./scripts/stack-up.sh
```

### Daily operations

```bash
# Start/stop all stacks
./scripts/stack-up.sh
./scripts/stack-down.sh

# Start/stop individual stack
./scripts/stack-up.sh --stack fazle-ai
./scripts/stack-down.sh --stack dograh

# Check status
./scripts/stack-status.sh
```

### Updating a single stack

```bash
# Example: rebuild and restart only Fazle services
cd fazle-ai
docker compose --env-file ../.env -p fazle-ai up -d --build fazle-llm-gateway
```

## Changes Made in Phase 6

### Priority 1 (HIGH) — Three-Stack Layout
- Created `ai-infra/docker-compose.yaml` — infrastructure services + LiveKit/Coturn/Cloudflared + monitoring
- Created `dograh/docker-compose.yaml` — Dograh API + UI only
- Created `fazle-ai/docker-compose.yaml` — all 12 Fazle services
- Cross-compose dependencies handled by `restart: unless-stopped` + `healthcheck` with generous `start_period`

### Priority 2 (HIGH) — Health Endpoints
- `fazle-system/queue/main.py` — Returns HTTP 503 when degraded (was always 200)
- `fazle-system/workers/main.py` — Returns HTTP 503 when degraded (was always 200)

### Priority 3 (MEDIUM) — Restart Policy
- Changed all services from `restart: always` to `restart: unless-stopped`
- Prevents containers from auto-starting after intentional `docker compose down`

### Priority 4 (MEDIUM) — Pinned Dependencies
- `fazle-system/api/requirements.txt` — Pinned `PyPDF2==3.0.1`, `python-docx==1.1.2`
- All other services already had pinned dependencies

### Priority 5 (LOW) — Grafana Dashboards
- Created `configs/grafana/provisioning/dashboards/dashboards.yml`
- Created `monitoring/grafana/dashboards/system-overview.json` — CPU, memory, disk, containers
- Created `monitoring/grafana/dashboards/fazle-services.json` — Service health, LLM gateway, queue/workers

### Priority 6 (LOW) — Redis Persistence
- Added `--save 300 10` — snapshot every 5 min if 10+ keys changed
- Added `--appendfsync everysec` — fsync AOF every second
- Added `--aof-use-rdb-preamble yes` — faster AOF loading

### Additional — Prometheus
- Added scrape targets for all 10 Fazle services (was only scraping fazle-api)
- Uses `dns_sd_configs` for fazle-workers to auto-discover replicas

## Files Modified

| File | Change |
|------|--------|
| `ai-infra/docker-compose.yaml` | Added LiveKit/Coturn/Cloudflared, restart policy, Redis persistence, Grafana mount |
| `dograh/docker-compose.yaml` | Created (API + UI only, clean separation) |
| `fazle-ai/docker-compose.yaml` | Created (all Fazle services, correct OLLAMA_MODEL defaults) |
| `fazle-system/queue/main.py` | Health endpoint returns 503 on failure |
| `fazle-system/workers/main.py` | Health endpoint returns 503 on failure |
| `fazle-system/api/requirements.txt` | Pinned PyPDF2, python-docx |
| `configs/prometheus/prometheus.yml` | Added 10 Fazle service scrape targets |
| `configs/grafana/provisioning/dashboards/dashboards.yml` | Dashboard auto-provisioning |
| `monitoring/grafana/dashboards/*.json` | System overview + Fazle services dashboards |
| `scripts/create-networks.sh` | Create 4 external Docker networks |
| `scripts/stack-up.sh` | Start stacks in correct order |
| `scripts/stack-down.sh` | Stop stacks in reverse order |
| `scripts/stack-status.sh` | Show health of all stacks |
| `verify-remediation.sh` | Added Phase 6 verification checks |

## Rollback

The original monolithic `docker-compose.yaml` is preserved in the root directory. To roll back:

```bash
# Stop three-stack deployment
./scripts/stack-down.sh

# Start monolithic deployment
docker compose up -d
```

## Key Constraints Preserved

- No networks, volumes, container names, or database names were renamed
- All exposed ports and Nginx routing remain unchanged
- Redis DB allocations unchanged (0-5)
- Old compose files (`dograh/dograh-docker-compose.yaml`, `fazle-ai/fazle-docker-compose.yaml`) kept as reference
