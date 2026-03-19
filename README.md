# Dograh + Fazle AI — Voice Agent SaaS Platform

> AI-powered voice agent platform with a personal intelligence layer. Handles real-time phone calls via Twilio SIP and LiveKit WebRTC, backed by a self-improving AI brain that learns from every interaction.

**Domain:** `iamazim.com` &nbsp;|&nbsp; **VPS:** Contabo (4 CPUs, 8 GB RAM, Ubuntu)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Services](#services)
  - [Stack 1 — ai-infra (Foundation)](#stack-1--ai-infra-foundation)
  - [Stack 2 — dograh (Voice Platform)](#stack-2--dograh-voice-platform)
  - [Stack 3 — fazle-ai (Intelligence Layer)](#stack-3--fazle-ai-intelligence-layer)
  - [Auxiliary — AI Watchdog & Control Plane](#auxiliary--ai-watchdog--control-plane)
- [Fazle Personal AI System](#fazle-personal-ai-system)
- [Networking & Domains](#networking--domains)
- [Monitoring Stack](#monitoring-stack)
- [Database](#database)
- [Security](#security)
- [Deployment](#deployment)
  - [Prerequisites](#prerequisites)
  - [Quick Start](#quick-start)
  - [Zero-Downtime Rolling Deploy](#zero-downtime-rolling-deploy)
  - [Rollback](#rollback)
- [Scripts Reference](#scripts-reference)
- [Secrets Management](#secrets-management)
- [Testing](#testing)
- [Configuration Files](#configuration-files)
- [Roadmap](#roadmap)
- [License](#license)

---

## Overview

The platform combines two systems:

| System | Purpose |
|--------|---------|
| **Dograh** | Open-source voice AI SaaS — handles inbound/outbound phone calls with real-time STT/TTS, LiveKit WebRTC streaming, and Twilio SIP integration. |
| **Fazle** | Custom personal AI layer — autonomous reasoning, semantic memory, relationship-aware personality, self-improving learning engine, and voice cloning. |

Together they deliver an AI voice clone that answers phone calls, remembers conversations, learns user preferences, and maintains relationship-specific behavior (family, friends, professional contacts) with content safety boundaries.

**Key capabilities:**
- Real-time voice call handling (Twilio → LiveKit → STT → LLM → TTS)
- Personality injection with relationship-aware context
- Semantic memory search over all past conversations (Qdrant vectors)
- Self-improving learning engine that extracts preferences and updates the relationship graph
- LLM gateway with caching, rate limiting, request batching, and OpenAI ↔ Ollama fallback
- Async task queue with auto-scaling workers
- Full observability: Prometheus + Grafana + Loki + Promtail
- Self-healing infrastructure via AI Watchdog and AI Control Plane
- Zero-downtime blue/green deployments
- Row-Level Security on all database tables

---

## Architecture

```
                          ┌──────────────────────┐
                          │      Nginx (SSL)     │
                          │  iamazim.com :443     │
                          └──┬─────┬─────┬────┬──┘
                             │     │     │    │
              ┌──────────────┘     │     │    └──────────────┐
              ▼                    ▼     ▼                   ▼
       ┌─────────────┐   ┌────────────┐ ┌──────────┐  ┌───────────┐
       │ Dograh UI   │   │ Dograh API │ │ LiveKit  │  │ Fazle UI  │
       │ :3010       │   │ :8000      │ │ :7880    │  │ :3020     │
       └─────────────┘   └─────┬──────┘ └────┬─────┘  └─────┬─────┘
                               │              │              │
                        ┌──────▼──────────────▼──────────────▼──────┐
                        │              Fazle AI Services             │
                        │                                            │
                        │  ┌─────────┐  ┌────────┐  ┌────────────┐ │
                        │  │  Brain  │  │ Memory │  │ LLM Gateway│ │
                        │  │  :8200  │  │ :8300  │  │   :8800    │ │
                        │  └────┬────┘  └────┬───┘  └─────┬──────┘ │
                        │       │            │            │         │
                        │  ┌────▼────┐  ┌────▼───┐  ┌────▼──────┐ │
                        │  │ Tasks   │  │Trainer │  │  Queue    │ │
                        │  │ :8400   │  │ :8600  │  │  :8810    │ │
                        │  └─────────┘  └────────┘  └────┬──────┘ │
                        │                                │         │
                        │  ┌──────────┐  ┌──────────┐ ┌──▼──────┐ │
                        │  │  Voice   │  │ Learning │ │ Workers │ │
                        │  │  :8700   │  │  :8900   │ │ :8820×4 │ │
                        │  └──────────┘  └──────────┘ └─────────┘ │
                        │  ┌──────────────────┐                    │
                        │  │ Web Intelligence │                    │
                        │  │     :8500        │                    │
                        │  └──────────────────┘                    │
                        └───────────────┬──────────────────────────┘
                                        │
              ┌─────────────────────────┼───────────────────────────┐
              │        Foundation (ai-infra)                        │
              │                                                     │
              │  PostgreSQL+pgvector  Redis  Qdrant  MinIO  Ollama │
              │  :5432               :6379  :6333   :9000  :11434  │
              │                                                     │
              │  LiveKit  Coturn  Prometheus  Grafana  Loki        │
              │  :7880    :3478   :9090       :3030    :3100       │
              └─────────────────────────────────────────────────────┘
```

---

## Services

The system deploys as **three Docker Compose stacks** started in order.

### Stack 1 — ai-infra (Foundation)

All shared infrastructure. Must start first.

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| postgres | `pgvector/pgvector:pg17` | 5432 | PostgreSQL 17 + pgvector embeddings |
| redis | `redis:7.2.5-alpine` | 6379 | Cache, pub/sub, streams, session store |
| minio | `minio/minio:2025-09-07` | 9000 / 9001 | S3-compatible object storage (recordings, files) |
| livekit | `livekit/livekit-server:v1.8.2` | 7880 / 7881 | WebRTC server for real-time audio |
| qdrant | `qdrant/qdrant:v1.17.0` | 6333 | Vector database for semantic memory |
| ollama | `ollama/ollama:0.3.14` | 11434 | Local LLM (fallback when OpenAI is unavailable) |
| coturn | `coturn/coturn:4.6.2` | 3478 / 5349 | TURN/STUN NAT traversal for WebRTC |
| prometheus | `prom/prometheus:latest` | 9090 | Metrics collection |
| grafana | `grafana/grafana:latest` | 3030 | Monitoring dashboards |
| loki | `grafana/loki:latest` | 3100 | Log aggregation |
| promtail | `grafana/promtail:latest` | 9080 | Log shipping → Loki |
| node-exporter | `prom/node-exporter:latest` | 9100 | Host-level metrics |
| cadvisor | `gcr.io/cadvisor/cadvisor:latest` | 8080 | Container metrics |

### Stack 2 — dograh (Voice Platform)

Pre-built Dograh containers for voice call handling.

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| api | `dograhai/dograh-api:1.0.0` | 8000 | FastAPI backend — call routing, STT/TTS, webhooks |
| ui | `dograhai/dograh-ui:1.0.0` | 3010 | Next.js dashboard — call management |

### Stack 3 — fazle-ai (Intelligence Layer)

Custom-built Fazle services. Each builds from `fazle-system/`.

| Service | Port | Purpose |
|---------|------|---------|
| fazle-api | 8100 | API Gateway — routing, JWT auth, rate limiting |
| fazle-brain | 8200 | Reasoning engine — LLM routing, personality injection |
| fazle-memory | 8300 | Vector memory — Qdrant semantic search, context retrieval |
| fazle-task-engine | 8400 | Scheduler — reminders, recurring tasks (APScheduler) |
| fazle-web-intelligence | 8500 | Web search & scraping (Serper API, BeautifulSoup) |
| fazle-trainer | 8600 | ML training — preference extraction, fine-tuning |
| fazle-voice | 8700 | Voice processing — accent modulation, cloning |
| fazle-ui | 3020 | Next.js dashboard — settings, conversation history |
| fazle-llm-gateway | 8800 | Centralized LLM routing with cache & rate limits |
| fazle-queue | 8810 | Async request queue (Redis Streams) |
| fazle-learning-engine | 8900 | Self-improvement — conversation analysis, knowledge extraction |
| fazle-workers | 8820 | Worker pool (4 replicas) consuming from queue |

### Auxiliary — AI Watchdog & Control Plane

| Component | Purpose |
|-----------|---------|
| **AI Watchdog** | Self-healing monitor — checks containers every 30 s, auto-restarts unhealthy services, manages disk space, auto-scales workers based on queue depth. |
| **AI Control Plane** | LLM-powered DevOps agent — snapshots system state every 60 s, uses AI reasoning to diagnose issues and execute repairs (restart, scale, cleanup). Produces daily JSON reports. |

---

## Fazle Personal AI System

Fazle is a layered intelligence system composed of 11 microservices:

```
Layer 1  API Gateway (fazle-api)
           ├── JWT auth, rate limiting, request routing
           │
Layer 2  Brain (fazle-brain)                 Memory (fazle-memory)
           ├── LLM reasoning                   ├── Qdrant vector search
           ├── Personality injection            ├── Embedding generation
           └── Decision making                  └── Context retrieval
           │
Layer 3  Tasks (fazle-task-engine)           Tools (fazle-web-intelligence)
           ├── Scheduling (APScheduler)         ├── Web search (Serper)
           └── Reminders & automation           └── Scraping + summarization
           │
         Trainer (fazle-trainer)
           ├── Preference extraction
           └── Fine-tuning
           │
Layer 4  LLM Gateway (fazle-llm-gateway)    Learning Engine (fazle-learning-engine)
           ├── Response caching (300 s TTL)     ├── Conversation analysis
           ├── Rate limiting (10 req/s)         ├── Relationship graph updates
           ├── Request batching (75 ms / 4)     ├── Correction processing
           └── Model fallback (OpenAI → Ollama) └── Nightly batch learning
           │
         Queue (fazle-queue) + Workers (fazle-workers × 4)
           ├── Redis Streams consumer group
           ├── Async request handling
           └── Auto-scaling (2–4 workers)
           │
Layer 5  Voice (fazle-voice)                 UI (fazle-ui)
           ├── Accent/tone personalization      ├── Next.js dashboard
           └── Voice cloning                    └── Settings & history
```

### How a call flows

1. Incoming Twilio SIP call → **Dograh API** receives webhook
2. Audio streamed via **LiveKit** WebRTC room
3. Real-time STT transcribes caller speech
4. **Fazle Brain** receives transcript, queries **Memory** for context
5. **LLM Gateway** generates a response (cached / rate-limited / batched)
6. Response injected with personality from `personality/*.md`
7. TTS converts response to audio, streamed back via LiveKit
8. **Learning Engine** asynchronously analyzes the conversation
9. **Memory** stores embeddings; **Trainer** extracts preferences

---

## Networking & Domains

### Docker Networks

| Network | Scope | Purpose |
|---------|-------|---------|
| `app-network` | Bridged | Connects Dograh + Fazle front-end services |
| `db-network` | Internal | PostgreSQL, Redis, MinIO, Qdrant (not externally reachable) |
| `ai-network` | Internal | Fazle AI services inter-communication |
| `monitoring-network` | Internal | Prometheus, Grafana, Loki, Promtail |

### Nginx Reverse Proxy (SSL)

| Domain | Backend | Port |
|--------|---------|------|
| `iamazim.com` | dograh-ui | 3010 |
| `api.iamazim.com` | dograh-api | 8000 |
| `livekit.iamazim.com` | livekit | 7880 |
| `fazle.iamazim.com` | fazle-ui / fazle-api | 3020 / 8100 |

### Externally Exposed Ports

| Port | Protocol | Service |
|------|----------|---------|
| 80 | TCP | Nginx (HTTP → HTTPS redirect) |
| 443 | TCP | Nginx (SSL termination) |
| 3478 | TCP/UDP | Coturn STUN/TURN |
| 5349 | TCP/UDP | Coturn TURN over TLS |
| 7881 | TCP | LiveKit RTC (direct, not proxied) |
| 49152–49252 | UDP | Coturn relay range |
| 50000–50200 | UDP | LiveKit WebRTC media range |

---

## Monitoring Stack

**Prometheus → Grafana → Loki → Promtail**

| Component | Port | Function |
|-----------|------|----------|
| Prometheus | 9090 | Scrapes metrics from all services (15 min retention) |
| Grafana | 3030 | Dashboards and alerting |
| Loki | 3100 | Centralized log storage |
| Promtail | 9080 | Ships Docker container logs to Loki |
| node-exporter | 9100 | Host CPU, memory, disk, network metrics |
| cAdvisor | 8080 | Per-container resource metrics |

**Metrics collected:** CPU/memory/disk (host + container), PostgreSQL queries, Redis operations, LiveKit status, LLM gateway cache hit rates, queue depth, worker throughput, and per-service Prometheus client metrics.

---

## Database

**PostgreSQL 17** with **pgvector** and **uuid-ossp** extensions.

### Core Tables

| Table | Scope | Purpose |
|-------|-------|---------|
| `calls` | Dograh | Call history (caller, duration, recordings, status) |
| `messages` | Dograh | Call transcripts (speaker, timestamp, text) |
| `voice_configurations` | Dograh | Per-contact voice/personality settings |
| `call_logs` | Dograh | Audit trail |
| `fazle_conversation_history` | Fazle | All chats & interactions |
| `fazle_audit_log` | Fazle | Append-only audit log (RLS enforced) |
| `fazle_relationship_graph` | Fazle | Contacts, relationships, interaction counts |
| `fazle_corrections` | Fazle | User corrections to AI responses |
| `fazle_learning_runs` | Fazle | Learning job history |
| `fazle_scheduler_jobs` | Fazle | Scheduled tasks & reminders |
| `fazle_web_intelligence_cache` | Fazle | Cached web search results & summaries |

### Vector Storage

**Qdrant** stores conversation embeddings for semantic search across all past interactions.

---

## Security

| Layer | Implementation |
|-------|---------------|
| **Authentication** | JWT tokens (PyJWT) + bcrypt password hashing |
| **Service-to-service auth** | FAZLE_API_KEY with `hmac.compare_digest` (timing-safe) |
| **Row-Level Security** | RLS policies via `_rls_conn()` on all tables — user isolation enforced at DB level |
| **Audit logging** | Append-only `fazle_audit_log` table (RLS prevents updates/deletes) |
| **Transport** | HTTPS everywhere + HSTS; HTTP → HTTPS redirect |
| **CORS** | Restricted to `iamazim.com` and `fazle.iamazim.com` |
| **Input validation** | Pydantic schemas with length limits and regex patterns |
| **Content safety** | OpenAI Moderation API with stricter thresholds for child accounts |
| **SSRF protection** | Private IP blocking on web scraper endpoints |
| **Container hardening** | Read-only filesystems, resource limits, pinned image versions |
| **Network isolation** | `db-network` and `monitoring-network` are Docker internal networks |
| **Secrets** | All critical secrets use `${VAR:?}` fail-fast; never echoed to logs |
| **Database hardening** | Password complexity, connection limits, query timeouts |
| **API docs blocked** | `/docs` and `/openapi.json` disabled in production Nginx |

---

## Deployment

### Prerequisites

- Ubuntu VPS with Docker and Docker Compose v2
- Domain pointed to VPS IP (`iamazim.com` + subdomains)
- Let's Encrypt SSL certificates (use `scripts/setup-ssl.sh`)
- UFW firewall configured (use `scripts/setup-firewall.sh`)
- `.env` file with all required secrets (see [Secrets Management](#secrets-management))

### Quick Start

```bash
# 1. Clone and enter directory
git clone <repo-url> vps-deploy && cd vps-deploy

# 2. Generate secrets
./scripts/gen-secrets.sh

# 3. Create Docker networks
./scripts/create-networks.sh

# 4. Start foundation services
cd ai-infra && docker compose up -d && cd ..

# 5. Run database migrations
./scripts/db-migrate.sh

# 6. Start voice platform
cd dograh && docker compose -f dograh-docker-compose.yaml up -d && cd ..

# 7. Start Fazle AI
cd fazle-ai && docker compose -f fazle-docker-compose.yaml up -d && cd ..

# 8. Verify all services
./scripts/health-check.sh
```

### Full VPS Deployment

```bash
# Deploys via SSH: backup → upload → extract → rebuild → migrate → healthcheck
./scripts/deploy-to-vps.sh
```

### Zero-Downtime Rolling Deploy

For **fazle-api** (blue/green via Nginx):

```bash
./scripts/deploy-rolling.sh
```

Process:
1. Build new image
2. Start on green port (8102) alongside blue (8101)
3. Health check the green instance
4. Switch Nginx upstream to both → drain → switch to green only
5. Stop blue

For **internal services** (brain, memory, etc.): Docker DNS round-robin during transition.

### Rollback

```bash
# Reverts to previous image tag (rolling-previous)
./scripts/rollback-rolling.sh

# Full VPS rollback to previous commit
./scripts/rollback-vps.sh
```

### Stack Management

```bash
./scripts/stack-up.sh       # Start all 3 stacks
./scripts/stack-down.sh     # Stop all 3 stacks
./scripts/stack-status.sh   # Health status of all services
```

---

## Scripts Reference

### Deployment & Infrastructure

| Script | Purpose |
|--------|---------|
| `deploy-to-vps.sh` | Full VPS deployment via SSH |
| `rollback-vps.sh` | Rollback to previous commit |
| `deploy-rolling.sh` | Zero-downtime blue/green deploy |
| `rollback-rolling.sh` | Rollback rolling deployment |
| `deploy-phase6.sh` | Deploy three-stack architecture |
| `migration-deploy.sh` | Migrate single-compose → 3 stacks |
| `db-migrate.sh` | Run PostgreSQL migrations |
| `setup-ssl.sh` | Generate Let's Encrypt certificates |
| `setup-firewall.sh` | Configure UFW rules |
| `setup-minio.sh` | Initialize MinIO buckets |
| `setup-ollama.sh` | Pull Ollama models |
| `create-networks.sh` | Create Docker networks |

### Stack Management

| Script | Purpose |
|--------|---------|
| `stack-up.sh` | Start all services |
| `stack-down.sh` | Stop all services |
| `stack-status.sh` | Check health status of all containers |

### Monitoring & Debugging

| Script | Purpose |
|--------|---------|
| `health-check.sh` | Verify all services are healthy |
| `check-monitoring.sh` | Verify Prometheus/Grafana/Loki pipeline |
| `check-livekit-api.py` | Test LiveKit connectivity |
| `check-watchdog-prereqs.sh` | Verify AI watchdog dependencies |
| `debug.sh` | Detailed system diagnostics |
| `diagnose.sh` | Troubleshoot common issues |
| `load-test.py` | Performance / concurrency testing |

### Data & Configuration

| Script | Purpose |
|--------|---------|
| `gen-secrets.sh` | Generate / rotate secrets |
| `backup.sh` | Backup PostgreSQL, Qdrant, Redis, MinIO (7-day retention) |
| `verify-configs.sh` | Validate all config files |
| `verify-remediation.sh` | Verify security audit fixes |
| `set-persona-overrides.py` | Configure voice personality |
| `seed-family.py` | Initialize family relationships |

### Testing & Integration

| Script | Purpose |
|--------|---------|
| `test-login.sh` | Test authentication flow |
| `test-fazle.sh` | Test Fazle API endpoints |
| `test-api-dns.py` / `.js` | DNS resolution tests |
| `test-openai-final.py` | OpenAI integration test |
| `test-multimodal.sh` | Multi-modal LLM tests |
| `test-full-login.sh` | End-to-end login flow |

---

## Secrets Management

Secrets are generated and managed by `scripts/gen-secrets.sh` and stored in `.env`.

### Managed Secrets

| Variable | Purpose | Rotation Impact |
|----------|---------|-----------------|
| `POSTGRES_PASSWORD` | Database auth | DB restart required |
| `REDIS_PASSWORD` | Redis auth | All Redis clients restart |
| `MINIO_SECRET_KEY` | S3 storage auth | Invalidates S3 access |
| `MINIO_ACCESS_KEY` | S3 storage credentials | MinIO credential change |
| `OSS_JWT_SECRET` | Dograh JWT signing | All Dograh sessions invalidated |
| `LIVEKIT_API_KEY` | LiveKit auth | Breaks active voice calls |
| `LIVEKIT_API_SECRET` | LiveKit auth | Breaks active voice calls |
| `TURN_SECRET` | Coturn auth | Breaks NAT traversal |
| `FAZLE_API_KEY` | Fazle service-to-service auth | Breaks Fazle internal calls |
| `FAZLE_JWT_SECRET` | Fazle JWT signing | Invalidates user sessions |
| `NEXTAUTH_SECRET` | Fazle UI session signing | Invalidates UI sessions |
| `GRAFANA_PASSWORD` | Grafana login | Only Grafana affected |

### Commands

```bash
./scripts/gen-secrets.sh                    # Generate missing secrets
./scripts/gen-secrets.sh --check            # Verify all secrets present
./scripts/gen-secrets.sh --rotate-all       # Rotate all (use with caution)
./scripts/gen-secrets.sh --rotate VAR1,VAR2 # Rotate specific secrets
./scripts/gen-secrets.sh --env-file /path   # Custom .env file
```

Security properties:
- `.env` created with `chmod 600`
- Atomic writes (temp file + `mv`)
- Cryptographic randomness via `openssl rand`
- Secrets never echoed to stdout

---

## Testing

**Framework:** pytest with `asyncio_mode = auto`

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_llm_gateway.py
```

### Test Coverage

| Test File | Area |
|-----------|------|
| `test_learning_engine.py` | Learning service functionality |
| `test_llm_gateway.py` | LLM gateway caching & rate limiting |
| `test_persona_evolution.py` | Personality update logic |
| `test_safety_fail_closed.py` | Content moderation fail-closed behavior |

Integration tests are available as shell scripts in `scripts/test-*.sh`.

---

## Configuration Files

```
configs/
├── coturn/
│   └── turnserver.conf         # TURN/STUN server (realm: iamazim.com)
├── grafana/                    # Grafana dashboards & data sources
├── livekit/
│   └── livekit.yaml            # WebRTC config (ports, webhooks, Redis backend)
├── loki/
│   └── loki.yaml               # Log aggregation server config
├── nginx/                      # Reverse proxy configs for 4 domains
├── prometheus/
│   └── prometheus.yaml         # Metric scrape targets
└── promtail/
    └── promtail.yaml           # Log shipper config → Loki
```

Additional configs:
- `personality/personality.md` — Master personality definition
- `personality/azim-master-persona.md` — Detailed persona rules, relationship boundaries, content safety
- `db/rls/rls_policies.sql` — Row-Level Security policies
- `db/hardening/` — Database hardening scripts

---

## Roadmap

Key planned features (from `yet-to-develop.txt`):

- **Voice AI Training** — Custom voice model training pipeline
- **Voice Cloning** — Full voice clone with accent/tone personalization
- **Behavior Improvement** — Enhanced learning from corrections and conversation patterns
- **PII Redaction** — Strip personal data before storing extracted knowledge
- **PWA Support** — Service worker, manifest, and offline capabilities
- **CI/CD Pipeline** — Automated testing and deployment
- **Coturn Rootless** — Run Coturn with `CAP_NET_BIND_SERVICE` instead of root

---

## License

Private / proprietary. All rights reserved.
