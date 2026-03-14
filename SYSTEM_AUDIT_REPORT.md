# ============================================================
# SYSTEM AUDIT REPORT — Production State Blueprint
# AI Voice Agent SaaS Platform (iamazim.com)
# Date: 2026-03-15 (Updated post Phase 4+5 deployment)
# ============================================================

---

## STEP 1 — PROJECT STRUCTURE ANALYSIS

### Full Directory Tree

```
e:\Programs\vps-deploy/
│
├── ROOT FILES:
│   ├── .env.example                  # Environment template (main)
│   ├── .env.local                    # Local testing secrets (gitignored)
│   ├── .gitattributes
│   ├── .gitignore
│   ├── .pre-commit-config.yaml
│   ├── docker-compose.yaml           # ★ MAIN compose — ALL 30 services
│   ├── dograh-docker-compose.yaml    # ★ ALTERNATIVE Dograh-only compose
│   ├── dograh.env.template           # Dograh-specific env template
│   ├── gen-secrets.sh
│   ├── production_readme.md
│   ├── pytest.ini
│   ├── verify-remediation.sh
│   ├── yet-to-develop.txt
│   ├── AUDIT_REPORT.md
│   ├── AUDIT_REPORT_2026-03-10.md
│   ├── DEPLOYMENT_MANIFEST.md
│   ├── INFRASTRUCTURE_AUDIT_REPORT.md
│   ├── LOCAL_REMEDIATION_REPORT.md
│   ├── PHASE4_5_DEPLOYMENT_REPORT.md # Phase 4+5 deployment report
│   ├── PRE_DEPLOY_CHECKLIST.md
│   ├── UPGRADE_ROADMAP.md
│   └── VERIFICATION_REPORT.md
│
├── configs/
│   ├── coturn/
│   │   └── turnserver.conf           # TURN/STUN server config
│   ├── grafana/
│   │   └── provisioning/
│   │       └── datasources/
│   │           └── datasources.yml   # Prometheus + Loki datasources
│   ├── livekit/
│   │   └── livekit.yaml              # LiveKit WebRTC server config
│   ├── loki/
│   │   └── loki.yml                  # Log aggregation config
│   ├── nginx/
│   │   ├── iamazim.com.conf          # Main domain routing
│   │   ├── api.iamazim.com.conf      # API subdomain
│   │   ├── fazle.iamazim.com.conf    # Fazle AI subdomain
│   │   └── livekit.iamazim.com.conf  # LiveKit subdomain
│   ├── prometheus/
│   │   └── prometheus.yml            # Metrics scraping config
│   └── promtail/
│       └── promtail.yml              # Docker log shipping
│
├── db/
│   ├── hardening/
│   │   └── roles_and_grants.sql      # Least-privilege DB roles
│   └── rls/
│       └── rls_policies_idempotent.sql  # Row-level security policies
│
├── deployment-package/
│   ├── .env.secure
│   ├── fix-secrets.sh
│   ├── MANIFEST.txt
│   ├── ROLLBACK_TARGET.txt
│   └── vps-deploy-*.tar.gz (×4)     # Deployment archives
│
├── docs/
│   ├── phase1-verify.md
│   ├── phase2-firewall-ports.md
│   ├── phase3-tls-certbot-coturn.md
│   ├── phase4-db-rls-hardening.md
│   └── secrets-rotation.md
│
├── fazle-system/                     # ★ Fazle Personal AI System
│   ├── .env.example                  # Fazle-specific env template
│   ├── README.md
│   ├── api/                          # API Gateway (port 8100)
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   ├── auth.py
│   │   ├── database.py
│   │   ├── audit.py
│   │   ├── schemas.py
│   │   ├── requirements.txt
│   │   └── rls_policies.sql
│   ├── brain/                        # Core Reasoning (port 8200)
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   ├── memory_manager.py
│   │   ├── persona_engine.py
│   │   ├── safety.py
│   │   └── requirements.txt
│   ├── memory/                       # Vector Memory (port 8300)
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── tasks/                        # Task Engine (port 8400)
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── migrations/
│   │       ├── 001_scheduler_tables.sql
│   │       └── 002_fazle_core_tables.sql
│   ├── tools/                        # Web Intel (port 8500)
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── plugins/
│   │       ├── __init__.py
│   │       ├── calendar_plugin.py
│   │       ├── crm_plugin.py
│   │       └── email_plugin.py
│   ├── trainer/                      # Learning (port 8600)
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── voice/                        # Voice Agent (port 8700)
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── llm-gateway/                  # ★ LLM Gateway (port 8800) — Phase 4
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── learning-engine/              # ★ Learning Engine (port 8900) — Phase 4
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── queue/                        # ★ Async Queue (port 8810) — Phase 5
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── workers/                      # ★ Worker Pool (port 8820) — Phase 5
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   └── requirements.txt
│   └── ui/                           # Fazle Dashboard (port 3020)
│       ├── Dockerfile
│       ├── package.json
│       ├── next.config.js
│       ├── middleware.js
│       ├── tailwind.config.js
│       ├── postcss.config.js
│       ├── public/
│       │   ├── manifest.json
│       │   └── sw.js
│       └── src/
│           ├── globals.css
│           ├── middleware.js
│           ├── components/
│           │   ├── AuthProvider.js
│           │   ├── ChatPanel.js
│           │   ├── KnowledgePanel.js
│           │   ├── MemoryPanel.js
│           │   ├── Sidebar.js
│           │   ├── TasksPanel.js
│           │   └── VoicePanel.js
│           └── app/
│               ├── layout.js
│               ├── page.js
│               ├── login/page.js
│               ├── dashboard/
│               │   ├── page.js
│               │   └── settings/voice/page.js
│               ├── admin/family/page.js
│               └── api/auth/[...nextauth]/route.js
│
├── local-validation/
│   ├── backup-docker-compose.yaml
│   ├── checklist.md
│   └── final-check.sh
│
├── monitoring/
│   └── grafana/
│       ├── dashboards/ (empty)
│       └── provisioning/
│           ├── alerting/ (empty)
│           └── dashboards/ (empty)
│
├── ops/
│   ├── letsencrypt/
│   │   └── deploy-hook-reload.sh
│   └── systemd/
│       └── docker-user-firewall.service
│
├── personality/
│   └── personality.md                # AI personality blueprint
│
├── scripts/
│   ├── backup.sh
│   ├── check-livekit-api.py
│   ├── check-monitoring.sh
│   ├── coturn-entrypoint.sh
│   ├── db-migrate.sh
│   ├── debug.sh
│   ├── deploy-to-vps.sh
│   ├── deploy.sh
│   ├── diagnose.sh
│   ├── gen-secrets.sh
│   ├── health-check-local.sh
│   ├── health-check.sh
│   ├── livekit-entrypoint.sh
│   ├── rollback-vps.sh
│   ├── rollback.sh
│   ├── seed-family.py
│   ├── setup-firewall.sh
│   ├── setup-ollama.sh
│   ├── setup-ssl.sh
│   ├── sudo-fix.sh
│   ├── sudo-setup.sh
│   ├── test-auth.sh
│   ├── test-browser-login.sh
│   ├── test-cookies.sh
│   ├── test-fazle.sh
│   ├── test-full-login.sh
│   ├── test-signup.sh
│   ├── ui-entrypoint.sh
│   ├── load-test.py                  # ★ Phase 4+5 load test script
│   ├── verify-configs.sh
│   └── vps/
│       ├── cert_expiry_metric.sh
│       ├── cert_san_check.sh
│       ├── cert_status.sh
│       ├── db_apply_rls.sh
│       ├── db_apply_roles.sh
│       ├── db_precheck.sh
│       ├── db_verify_rls.sh
│       ├── docker_user_firewall.sh
│       ├── install_certbot_deploy_hook.sh
│       ├── install_docker_user_firewall_service.sh
│       ├── ports_audit.sh
│       ├── turn_tls_check.sh
│       └── ufw_apply.sh
│
├── ai-infra/                         # ★ Three-stack layout (alternative)
│   └── docker-compose.yaml           #   Infrastructure + monitoring
│
├── dograh/                           # ★ Three-stack layout (alternative)
│   └── dograh-docker-compose.yaml    #   Dograh services
│
├── fazle-ai/                         # ★ Three-stack layout (alternative)
│   └── fazle-docker-compose.yaml     #   All Fazle services
│
└── tests/
    └── test_safety_fail_closed.py
```

### Summary Counts

| Category | Count |
|----------|-------|
| Docker Compose files | 5 (`docker-compose.yaml` main, `dograh-docker-compose.yaml`, `ai-infra/`, `fazle-ai/`, `local-validation/backup-docker-compose.yaml`) |
| Dockerfiles | 12 (api, brain, memory, tasks, tools, trainer, voice, ui, llm-gateway, learning-engine, queue, workers) |
| Environment files | 4 (`.env.example`, `.env.local`, `dograh.env.template`, `fazle-system/.env.example`) |
| Nginx configs | 4 (iamazim.com, api, fazle, livekit) |
| SQL migration files | 5 (2 in tasks/migrations, rls_policies.sql, db/rls, db/hardening) |
| Shell scripts | 37 (scripts/ + scripts/vps/ + load-test.py) |
| Python services | 11 (api, brain, memory, tasks, tools, trainer, voice, llm-gateway, learning-engine, queue, workers) |
| Next.js apps | 1 (fazle-system/ui) |

---

## STEP 2 — DOCKER & INFRASTRUCTURE ANALYSIS

### 2.1 — Docker Compose Files

#### File 1: `docker-compose.yaml` (MAIN — Production)

This is the **unified production compose** that runs ALL 30 services in a single stack. This is what runs on the VPS at `/home/azim/ai-call-platform/`.

#### File 2: `dograh-docker-compose.yaml` (ALTERNATIVE — Dograh-only)

A **standalone Dograh stack** with its own Postgres, Redis, MinIO, Nginx, Coturn, Cloudflared, API, and UI. Uses different env var prefixes (`DOGRAH_PG_*`, `DOGRAH_REDIS_*`, `DOGRAH_MINIO_*`).

**CRITICAL CONFLICT: These two compose files define duplicate infrastructure services (Postgres, Redis, MinIO) with different configurations. They are NOT meant to run simultaneously.**

#### Files 3-5: Three-Stack Layout (Alternative — Not active on VPS)

- `ai-infra/docker-compose.yaml` — Shared infrastructure (Postgres, Redis, MinIO, Qdrant, Ollama, monitoring)
- `dograh/dograh-docker-compose.yaml` — Dograh services only
- `fazle-ai/fazle-docker-compose.yaml` — All Fazle services

These were created for future migration but the VPS currently runs the monolithic `docker-compose.yaml`.

### 2.2 — Service Inventory (Main docker-compose.yaml)

| Service | Container Name | Internal Port | Exposed Port | Image | Build Context | Purpose |
|---------|---------------|---------------|-------------|-------|---------------|---------|
| postgres | ai-postgres | 5432 | NONE (internal) | pgvector/pgvector:pg17 | — | Primary database (pgvector) |
| redis | ai-redis | 6379 | NONE (internal) | redis:8.0.2-alpine | — | Cache, pub/sub, session store |
| minio | minio | 9000, 9001 | NONE (internal) | minio/minio:RELEASE.2025-09-07 | — | S3-compatible object storage |
| livekit | livekit | 7880 | 127.0.0.1:7880 | livekit/livekit-server:v1.8.2 | — | WebRTC audio/video |
| livekit (RTC) | livekit | 7881 | 0.0.0.0:7881 | — | — | RTC over TCP (direct) |
| livekit (UDP) | livekit | 50000-50200/udp | 0.0.0.0:50000-50200/udp | — | — | WebRTC UDP media |
| coturn | coturn | 3478, 5349 | 0.0.0.0:3478, 5349 | coturn/coturn:4.6.2-r12-alpine | — | TURN/STUN NAT traversal |
| coturn (relay) | coturn | 49152-49252/udp | 0.0.0.0:49152-49252/udp | — | — | TURN relay ports |
| api | dograh-api | 8000 | 127.0.0.1:8000 | dograhai/dograh-api:1.0.0 | — | Dograh backend (pre-built) |
| ui | dograh-ui | 3010 | 127.0.0.1:3010 | dograhai/dograh-ui:1.0.0 | — | Dograh dashboard (pre-built) |
| cloudflared | cloudflared-tunnel | 2000 | NONE | cloudflare/cloudflared:2024.10.1 | — | Cloudflare tunnel fallback |
| qdrant | qdrant | 6333 | NONE (internal) | qdrant/qdrant:v1.17.0 | — | Vector database |
| ollama | ollama | 11434 | NONE (internal) | ollama/ollama:0.3.14 | — | Local LLM server (protected) |
| fazle-api | fazle-api | 8100 | 127.0.0.1:8100 | — | ./fazle-system/api | Fazle API gateway |
| fazle-brain | fazle-brain | 8200 | NONE (internal) | — | ./fazle-system/brain | AI reasoning engine (uses LLM Gateway) |
| fazle-memory | fazle-memory | 8300 | NONE (internal) | — | ./fazle-system/memory | Vector memory system |
| fazle-task-engine | fazle-task-engine | 8400 | NONE (internal) | — | ./fazle-system/tasks | Task scheduler |
| fazle-web-intelligence | fazle-web-intelligence | 8500 | NONE (internal) | — | ./fazle-system/tools | Web search/scraping |
| fazle-trainer | fazle-trainer | 8600 | NONE (internal) | — | ./fazle-system/trainer | Knowledge extraction (uses LLM Gateway) |
| fazle-voice | fazle-voice | — | NONE (internal) | — | ./fazle-system/voice | LiveKit voice agent |
| fazle-ui | fazle-ui | 3020 | 127.0.0.1:3020 | — | ./fazle-system/ui | Fazle Next.js dashboard |
| **fazle-llm-gateway** | fazle-llm-gateway | **8800** | NONE (internal) | — | ./fazle-system/llm-gateway | **LLM routing, caching, rate limiting, batching** |
| **fazle-learning-engine** | fazle-learning-engine | **8900** | NONE (internal) | — | ./fazle-system/learning-engine | **Autonomous self-improvement** |
| **fazle-queue** | fazle-queue | **8810** | NONE (internal) | — | ./fazle-system/queue | **Redis Streams async request queue** |
| **fazle-workers** | — (replicated) | **8820** | NONE (internal) | — | ./fazle-system/workers | **LLM request worker pool (2 replicas)** |
| prometheus | prometheus | 9090 | NONE (internal) | prom/prometheus:v2.55.0 | — | Metrics collection |
| grafana | grafana | 3000 | 127.0.0.1:3030 | grafana/grafana:11.2.2 | — | Dashboards |
| node-exporter | node-exporter | 9100 | NONE (internal) | prom/node-exporter:v1.8.2 | — | Host metrics |
| cadvisor | cadvisor | 8080 | NONE (internal) | gcr.io/cadvisor/cadvisor:v0.49.1 | — | Container metrics |
| loki | loki | 3100 | NONE (internal) | grafana/loki:3.2.1 | — | Log aggregation |
| promtail | promtail | 9080 | NONE (internal) | grafana/promtail:3.2.1 | — | Log shipper |

**Total: 30 services defined (29 containers running — workers has 2 replicas)**

### 2.3 — Docker Volumes

| Volume | Used By | Purpose |
|--------|---------|---------|
| postgres_data | postgres | Database storage |
| redis_data | redis | Redis persistence |
| minio-data | minio | Object storage |
| shared-tmp | api, dograh-api | Shared temp files |
| qdrant_data | qdrant | Vector database storage |
| ollama_data | ollama | LLM model storage |
| prometheus_data | prometheus | Metrics storage |
| grafana_data | grafana | Dashboard storage |
| loki_data | loki | Log storage |

### 2.3a — Redis Database Allocation

| DB | Service | Purpose |
|----|---------|---------|
| 0 | Default (Dograh, LiveKit) | Session data, coordination |
| 1 | fazle-brain | Conversation cache (24h TTL) |
| 2 | fazle-trainer | Training session tracking |
| 3 | fazle-llm-gateway | LLM response cache, rate limit counters, usage tracking |
| 4 | fazle-learning-engine | Learning data, relationship graph |
| 5 | fazle-queue & fazle-workers | Redis Streams async queue |

### 2.4 — Docker Networks

| Network | Driver | Internal | Services |
|---------|--------|----------|----------|
| app-network | bridge | NO | livekit, coturn, dograh-api, dograh-ui, cloudflared, fazle-api, fazle-brain, fazle-memory, fazle-task-engine, fazle-web-intelligence, fazle-trainer, fazle-voice, fazle-ui, fazle-llm-gateway, prometheus, grafana |
| db-network | bridge | YES | postgres, redis, minio, qdrant, livekit, dograh-api, fazle-api, fazle-brain, fazle-memory, fazle-task-engine, fazle-llm-gateway, fazle-learning-engine, fazle-queue, fazle-workers |
| ai-network | bridge | YES | ollama, fazle-brain, fazle-memory, fazle-task-engine, fazle-web-intelligence, fazle-trainer, fazle-voice, fazle-llm-gateway, fazle-learning-engine, fazle-queue, fazle-workers |
| monitoring-network | bridge | YES | prometheus, grafana, node-exporter, cadvisor, loki, promtail |

### 2.5 — Duplicate/Conflict Analysis

| Issue | Severity | Detail |
|-------|----------|--------|
| **Two Compose Files with Overlapping Services** | CRITICAL | `docker-compose.yaml` and `dograh-docker-compose.yaml` both define postgres, redis, minio with different configs. They share volume names (`postgres_data`, `redis_data`, `minio-data`) — running both simultaneously would cause data corruption. |
| **Single PostgreSQL Instance** | OK | Only 1 Postgres in main compose (shared by Dograh + Fazle). Different DB name in dograh-compose (`dograh` vs `postgres`). |
| **Single Redis Instance** | OK | 1 Redis, but used with different DB numbers: DB 0 (Dograh/LiveKit), DB 1 (Brain), DB 2 (Trainer), DB 3 (LLM Gateway), DB 4 (Learning Engine), DB 5 (Queue/Workers). |
| **Single Ollama Instance** | OK | 1 Ollama, 6GB memory limit. Protected: NUM_PARALLEL=1, MAX_LOADED_MODELS=1, MAX_QUEUE=2. Only model: qwen2.5:3b (1.9GB). |
| **Container Name Conflicts** | WARNING | Both composes use `minio` as container name. If both run simultaneously, Docker will fail. |
| **Port Conflicts** | WARNING | dograh-compose exposes postgres (5432), redis (6379), minio (9000/9001) on 127.0.0.1 — main compose keeps them internal. Running both = port conflicts. |
| **Image Version Mismatch** | INFO | Redis: `redis:8.0.2-alpine` (main) vs `redis:7` (dograh). Coturn: `4.6.2-r12-alpine` (main) vs `4.8.0` (dograh). |

---

## STEP 3 — API STRUCTURE

### 3.1 — Dograh API (Pre-built Image — Port 8000)

The Dograh API is a **pre-built Docker image** (`dograhai/dograh-api`). Its routes are not in this repo but are known from Nginx config:

| Method | Path | Purpose |
|--------|------|---------|
| GET | /api/v1/health | Health check |
| * | /api/* | All Dograh API routes (via Nginx) |
| * | /telephony/* | Twilio webhook callbacks |
| * | /ws/* | WebSocket signaling |
| POST | /api/v1/livekit/webhook | LiveKit webhook receiver |
| * | /api/config/* | Frontend config (proxied to UI) |
| * | /api/auth/* | Frontend auth (proxied to UI) |

### 3.2 — Fazle API Gateway (Port 8100)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | /health | None | Health check |
| GET | /metrics | None | Prometheus metrics |
| POST | /auth/register | Admin JWT | Register family member |
| POST | /auth/login | None | Login with email/password |
| POST | /auth/setup | None (first-run only) | Initial admin setup |
| GET | /auth/me | JWT | Get current user |
| GET | /auth/family | Admin JWT | List all family members |
| PUT | /auth/family/{user_id} | Admin JWT | Update family member |
| DELETE | /auth/family/{user_id} | Admin JWT | Delete family member |
| GET | /auth/setup-status | None | Check if setup is complete |
| POST | /fazle/voice/token | JWT or API Key | Generate LiveKit token |
| POST | /fazle/decision | JWT or API Key | AI decision (Dograh integration) |
| POST | /fazle/chat | JWT or API Key | Text chat with Fazle brain |
| GET | /fazle/conversations | JWT or API Key | List chat conversations |
| GET | /fazle/conversations/{id} | JWT or API Key | Get conversation messages |
| POST | /fazle/memory | JWT or API Key | Store memory |
| POST | /fazle/memory/search | JWT or API Key | Search memories |
| DELETE | /fazle/memory/{memory_id} | JWT or API Key | Delete memory |
| POST | /fazle/knowledge/ingest | JWT or API Key | Ingest knowledge text |
| POST | /fazle/files/upload | JWT or API Key | Upload files for RAG |
| POST | /fazle/tasks | JWT or API Key | Create task |
| GET | /fazle/tasks | JWT or API Key | List tasks |
| POST | /fazle/web/search | JWT or API Key | Web search proxy |
| POST | /fazle/train | JWT or API Key | Train from transcript |
| GET | /fazle/status | JWT or API Key | System status (all services) |
| GET | /fazle/audit | Admin JWT | View audit logs |

### 3.3 — Fazle Brain (Port 8200, Internal Only)

| Method | Path | Purpose |
|--------|------|---------|
| GET | /health | Health check |
| GET | /metrics | Prometheus metrics |
| POST | /decide | AI decision for voice calls |
| POST | /chat | Interactive chat with memory/persona |

### 3.4 — Fazle Memory (Port 8300, Internal Only)

| Method | Path | Purpose |
|--------|------|---------|
| GET | /health | Health check |
| GET | /metrics | Prometheus metrics |
| POST | /store | Store memory with vector embedding |
| POST | /search | Semantic search across memories |
| POST | /ingest | Ingest knowledge text |
| DELETE | /memories/{id} | Delete memory |

### 3.5 — Fazle Task Engine (Port 8400, Internal Only)

| Method | Path | Purpose |
|--------|------|---------|
| GET | /health | Health check |
| GET | /metrics | Prometheus metrics |
| POST | /tasks | Create task |
| GET | /tasks | List tasks (filterable) |
| GET | /tasks/{id} | Get task |
| PATCH | /tasks/{id} | Update task |
| DELETE | /tasks/{id} | Delete task |

### 3.6 — Fazle Web Intelligence (Port 8500, Internal Only)

| Method | Path | Purpose |
|--------|------|---------|
| GET | /health | Health check |
| GET | /metrics | Prometheus metrics |
| POST | /search | Web search (Serper/Tavily) |
| POST | /scrape | Extract text from URL |
| POST | /summarize | Summarize URL/text content |

### 3.7 — Fazle Trainer (Port 8600, Internal Only)

| Method | Path | Purpose |
|--------|------|---------|
| GET | /health | Health check |
| POST | /train | Extract knowledge from transcript |

### 3.8 — Internal Service Call Map

```
Dograh API (8000) ──POST /fazle/decision──▶ Fazle API (8100)
                                              │
                                              ├──▶ Fazle Brain (8200)
                                              │      ├──▶ Fazle Memory (8300) [search/store]
                                              │      ├──▶ Fazle Web Intel (8500) [search]
                                              │      ├──▶ Fazle Task Engine (8400) [create_task]
                                              │      ├──▶ LLM Gateway (8800) [USE_LLM_GATEWAY=true]
                                              │      └──▶ Learning Engine (8900) [report conversations]
                                              │
                                              ├──▶ Fazle Memory (8300) [proxy]
                                              ├──▶ Fazle Task Engine (8400) [proxy]
                                              ├──▶ Fazle Web Intel (8500) [proxy]
                                              └──▶ Fazle Trainer (8600) [proxy]

LLM Gateway (8800) ──▶ OpenAI gpt-4o (primary)
                   ──▶ Ollama qwen2.5:3b (fallback)
                   ──▶ Redis DB 3 (cache, rate limits, usage)
                   Features: request batching (75ms window, max 4),
                             per-user rate limiting (10 req/s),
                             response caching (300s TTL),
                             model fallback on error

Fazle Queue (8810) ──▶ Redis DB 5 [Streams] ──▶ Fazle Workers ×2 (8820)
                                                  └──▶ LLM Gateway (8800)

Learning Engine (8900) ──▶ Redis DB 4 [relationship graph, corrections]
                       ──▶ Nightly learning cycle (autonomous)

Fazle Voice (no port) ──▶ LiveKit (7880) [WebRTC agent]
                       ──▶ Fazle Brain (8200) [query brain for responses]

Fazle Memory (8300) ──▶ Qdrant (6333) [vector store/search]
                    ──▶ OpenAI [embeddings API]

Fazle Trainer (8600) ──▶ LLM Gateway (8800) [USE_LLM_GATEWAY=true]
                     ──▶ Fazle Memory (8300) [store]
                     ──▶ Redis (DB 2) [session tracking]

Fazle Brain (8200) ──▶ Redis (DB 1) [conversation cache]
```

### 3.9 — New Phase 4+5 Service APIs

#### Fazle LLM Gateway (Port 8800, Internal Only)

| Method | Path | Purpose |
|--------|------|---------|
| GET | /health | Health check |
| GET | /metrics | Prometheus metrics |
| POST | /v1/chat/completions | LLM request routing (cached, rate-limited, batched) |
| POST | /v1/chat/completions/batch | Batch LLM requests |
| GET | /usage | Usage statistics |

#### Fazle Learning Engine (Port 8900, Internal Only)

| Method | Path | Purpose |
|--------|------|---------|
| GET | /health | Health check |
| POST | /analyze | Analyze conversation for learning |
| POST | /correct | Record user correction |
| GET | /insights | Get learning insights |

#### Fazle Queue (Port 8810, Internal Only)

| Method | Path | Purpose |
|--------|------|---------|
| GET | /health | Health check |
| POST | /submit | Submit async LLM request |
| GET | /status/{request_id} | Check request status |
| GET | /result/{request_id} | Get request result |

#### Fazle Workers (Port 8820, Internal Only — 2 replicas)

| Method | Path | Purpose |
|--------|------|---------|
| GET | /health | Health check |

### 3.10 — External APIs Used

| API | Used By | Purpose |
|-----|---------|---------|
| OpenAI Chat Completions | LLM Gateway (→ Brain, Trainer) | LLM reasoning (primary: gpt-4o) |
| OpenAI Embeddings | Memory | Vector embeddings (text-embedding-3-small) |
| OpenAI Moderation | Brain/Safety | Content safety filtering |
| OpenAI STT | Voice | Speech-to-text (Whisper) |
| OpenAI TTS | Voice | Text-to-speech |
| Ollama (local) | LLM Gateway (fallback) | Local LLM alternative (qwen2.5:3b) |
| Serper (Google) | Web Intelligence | Web search |
| Tavily | Web Intelligence | Web search (alternative) |
| Twilio | Dograh API | Phone calls via SIP |

---

## STEP 4 — DATABASE ANALYSIS

### 4.1 — PostgreSQL Instance

- **Image**: `pgvector/pgvector:pg17` (PostgreSQL 17 with pgvector extension)
- **Container**: `ai-postgres`
- **Database Name**: `postgres` (main compose) / `dograh` (dograh-compose)
- **User**: `postgres`
- **Connection**: Internal only via `db-network`

### 4.2 — Database Tables

#### Table: `fazle_users`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| email | VARCHAR(255) | UNIQUE NOT NULL |
| hashed_password | VARCHAR(255) | NOT NULL |
| name | VARCHAR(100) | NOT NULL |
| relationship_to_azim | VARCHAR(50) | NOT NULL DEFAULT 'self' |
| role | VARCHAR(20) | NOT NULL DEFAULT 'member' |
| is_active | BOOLEAN | DEFAULT true |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Indexes**: `idx_fazle_users_email` on `email`

#### Table: `fazle_conversations`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| user_id | UUID | NOT NULL REFERENCES fazle_users(id) ON DELETE CASCADE |
| conversation_id | VARCHAR(100) | NOT NULL, UNIQUE |
| title | VARCHAR(200) | DEFAULT '' |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Indexes**: `idx_fazle_conv_user` on `user_id`
**Foreign Key**: `user_id → fazle_users.id` (CASCADE)

#### Table: `fazle_messages`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| conversation_id | UUID | NOT NULL REFERENCES fazle_conversations(id) ON DELETE CASCADE |
| role | VARCHAR(20) | NOT NULL |
| content | TEXT | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Indexes**: `idx_fazle_msg_conv` on `conversation_id`
**Foreign Key**: `conversation_id → fazle_conversations.id` (CASCADE)

#### Table: `fazle_tasks`

| Column | Type | Constraints |
|--------|------|-------------|
| id | VARCHAR(36) | PRIMARY KEY |
| title | VARCHAR(500) | NOT NULL |
| description | TEXT | DEFAULT '' |
| task_type | VARCHAR(50) | NOT NULL DEFAULT 'reminder' |
| status | VARCHAR(50) | NOT NULL DEFAULT 'pending' |
| scheduled_at | TIMESTAMPTZ | NULLABLE |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |
| payload | JSONB | DEFAULT '{}'::jsonb |

**Indexes**: `idx_fazle_tasks_status`, `idx_fazle_tasks_type`, `idx_fazle_tasks_created`

#### Table: `fazle_audit_log`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| actor_id | VARCHAR(100) | NOT NULL |
| actor_email | VARCHAR(255) | NOT NULL DEFAULT '' |
| action | VARCHAR(100) | NOT NULL |
| target_type | VARCHAR(50) | NOT NULL DEFAULT '' |
| target_id | VARCHAR(100) | DEFAULT '' |
| detail | TEXT | DEFAULT '' |
| ip_address | VARCHAR(45) | DEFAULT '' |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() |

**Indexes**: `idx_audit_actor`, `idx_audit_action`, `idx_audit_created`

#### Table: `apscheduler_jobs` (auto-created by APScheduler)

Created automatically by SQLAlchemyJobStore. Used by fazle-task-engine.

#### Dograh Tables (managed by pre-built image — schema unknown)

The Dograh API creates its own tables via its built-in ORM (asyncpg + SQLAlchemy). The exact schema is inside the pre-built Docker image and is **not visible in this repo**. Dograh uses the same PostgreSQL instance and database.

### 4.3 — Row-Level Security (RLS)

RLS is enabled on:
- `fazle_conversations` — users see only their own conversations
- `fazle_messages` — users see only messages in their own conversations
- `fazle_audit_log` — append-only; SELECT restricted to admin

RLS uses `SET LOCAL app.current_user_id` session variable.

### 4.4 — DB Roles (Optional Hardening)

Defined roles (not yet activated):
- `fazle_app` — DML on fazle_* tables only
- `dograh_app` — DML on non-fazle tables
- `fazle_readonly` — read-only access

Currently, all services connect as `postgres` superuser.

### 4.5 — Other Data Stores

| Store | Purpose | Data |
|-------|---------|------|
| **Qdrant** (v1.17.0) | Vector database | Fazle memories (collection: `fazle_memories`), 1536-dim Cosine vectors |
| **Redis** (DB 0) | LiveKit coordination, Dograh cache | Session data |
| **Redis** (DB 1) | Brain conversation cache | Conversation history (24h TTL) |
| **Redis** (DB 2) | Trainer session tracking | Training sessions |
| **Redis** (DB 3) | LLM Gateway | Response cache (300s TTL), rate limit counters (10 req/s per user), usage stats |
| **Redis** (DB 4) | Learning Engine | Relationship graph, user corrections, learning data |
| **Redis** (DB 5) | Queue + Workers | Redis Streams for async LLM requests |
| **MinIO** | Object storage | Voice audio files (bucket: `voice-audio`) |
| **Ollama** | LLM model storage | Downloaded models (qwen2.5:3b — 1.9GB, 3.1B params) |

---

## STEP 5 — AI SYSTEM COMPONENTS

### 5.1 — AI Architecture

```
                    ┌────────────────────────────────────────────────────┐
                    │           Fazle AI System (Phase 4+5)             │
                    │                                                    │
 User Input ──────▶ │  API Gateway (8100)                                │
 (text/voice)       │       │                                            │
                    │       ▼                                            │
                    │  Brain (8200) ──────────────────────────────────┐  │
                    │   │ ├── Persona Engine (per-user tone)          │  │
                    │   │ ├── Safety Module (content filter)          │  │
                    │   │ ├── Conversation Memory (Redis DB 1)        │  │
                    │   │ └── Learning Reports → Learning Engine      │  │
                    │   │                                             │  │
                    │   ├──▶ LLM Gateway (8800) ★ NEW                 │  │
                    │   │     ├── Request Batching (75ms, max 4)      │  │
                    │   │     ├── Response Caching (Redis DB 3)       │  │
                    │   │     ├── Per-User Rate Limiting (10 req/s)   │  │
                    │   │     ├── Primary: OpenAI GPT-4o              │  │
                    │   │     └── Fallback: Ollama qwen2.5:3b         │  │
                    │   │                                             │  │
                    │   ├──▶ Memory Service (8300)                    │  │
                    │   │     ├── OpenAI Embeddings                   │  │
                    │   │     └── Qdrant Vector DB                    │  │
                    │   │                                             │  │
                    │   ├──▶ Web Intelligence (8500)                  │  │
                    │   │     ├── Serper / Tavily Search              │  │
                    │   │     └── Web Scraping + Extraction           │  │
                    │   │                                             │  │
                    │   └──▶ Task Engine (8400)                       │  │
                    │         ├── APScheduler (PostgreSQL)            │  │
                    │         └── Scheduled Actions                   │  │
                    │                                                 │  │
                    │  Async Queue (8810) ★ NEW                       │  │
                    │   ├── Redis Streams (DB 5) submit/poll          │  │
                    │   └── Workers ×2 (8820) ──▶ LLM Gateway        │  │
                    │                                                 │  │
                    │  Learning Engine (8900) ★ NEW                   │  │
                    │   ├── Conversation Analysis                     │  │
                    │   ├── Relationship Graph (Redis DB 4)           │  │
                    │   ├── User Correction Tracking                  │  │
                    │   └── Nightly Learning Cycle                    │  │
                    │                                                 │  │
                    │  Trainer (8600) ◀── Conversation logs           │  │
                    │   ├── PII Redaction                             │  │
                    │   ├── LLM Knowledge Extraction (via Gateway)    │  │
                    │   └── Store to Memory                           │  │
                    │                                                    │
                    │  Voice Agent (LiveKit Worker)                      │
                    │   ├── Silero VAD                                   │
                    │   ├── OpenAI Whisper (STT)                        │
                    │   ├── Brain Chat (LLM via Brain → Gateway)        │
                    │   └── OpenAI TTS (voice: alloy)                   │
                    └────────────────────────────────────────────────────┘
```

### 5.2 — AI Flow (Text Chat)

```
User → Fazle UI → NextAuth (JWT) → Fazle API Gateway → Safety Check →
  Brain Service → Retrieve Memories (Qdrant) → Build Persona Prompt →
  LLM Gateway (cache check → rate limit → batch → OpenAI/Ollama) →
  Extract Memory Updates → Store Memories (Qdrant) →
  Report to Learning Engine → Execute Actions → Response
```

### 5.3 — AI Flow (Voice)

```
User → Fazle UI → Get LiveKit Token → Connect to Room →
  Voice Agent (LiveKit Worker) → Silero VAD (detect speech) →
  OpenAI Whisper (transcribe) → Brain Service (think) →
  OpenAI TTS (speak) → Audio back to user
```

### 5.4 — AI Flow (Dograh Integration)

```
Phone Call → Twilio → Dograh API → POST /fazle/decision →
  Fazle API → Brain Service → Decision + Actions → Response to Dograh
```

### 5.5 — Persona Engine

Relationship-aware system prompts with 6 persona types:
- `self` — Internal monologue / self-assistant mode
- `wife` — Loving husband tone
- `daughter` — Caring father, age-appropriate
- `son` — Caring father, engaging
- `parent` — Respectful son
- `sibling` — Casual, brotherly

### 5.6 — Safety Module

- Uses OpenAI Moderation API
- Dual threshold system: DEFAULT_THRESHOLDS (adults), CHILD_THRESHOLDS (stricter for daughter/son)
- **Fails closed** for child accounts (blocks if moderation API is unavailable)
- **Fails open** for adult accounts (allows if moderation API is unavailable)

### 5.7 — Memory Types

5 memory categories stored in Qdrant:
- `preference` — User preferences
- `contact` — Contact information
- `knowledge` — Learned knowledge
- `personal` — Personal facts
- `conversation` — Conversation summaries

Embeddings: OpenAI `text-embedding-3-small` (1536 dimensions, Cosine distance)

---

## STEP 6 — UI SYSTEM

### 6.1 — Dograh UI (Pre-built Image)

- **Image**: `dograhai/dograh-ui`
- **Port**: 3010
- **Framework**: Unknown (pre-built, likely Next.js based on env vars)
- **Purpose**: Voice agent management dashboard
- **Access**: https://iamazim.com

### 6.2 — Fazle UI

- **Framework**: Next.js 14.2.35
- **React**: 18.3.1
- **Auth**: NextAuth.js 4.24.11 (credentials provider, JWT sessions)
- **Styling**: Tailwind CSS 3.4.17
- **Port**: 3020
- **Access**: https://fazle.iamazim.com
- **PWA**: Manifest included (service worker registered)

### 6.3 — Fazle UI Routes

| Route | Component | Auth Required | Purpose |
|-------|-----------|---------------|---------|
| `/` | page.js | No (redirects if logged in) | Login/landing page |
| `/login` | login/page.js | No | Login + first-time setup |
| `/dashboard` | dashboard/page.js | Yes (middleware) | Main dashboard |
| `/dashboard/settings/voice` | settings/voice/page.js | Yes | Voice settings |
| `/admin/family` | admin/family/page.js | Yes (admin) | Family member management |
| `/api/auth/*` | NextAuth routes | — | Auth API (NextAuth) |

### 6.4 — Fazle UI Dashboard Panels

| Panel | Component | API Integration |
|-------|-----------|-----------------|
| Chat | ChatPanel.js | POST /fazle/chat |
| Voice | VoicePanel.js | POST /fazle/voice/token → LiveKit |
| Memory | MemoryPanel.js | POST /fazle/memory/search, /fazle/memory |
| Tasks | TasksPanel.js | GET/POST /fazle/tasks |
| Knowledge | KnowledgePanel.js | POST /fazle/knowledge/ingest, /fazle/files/upload |

### 6.5 — UI API Integration

```
Fazle UI (Next.js)
  ├── NextAuth ──▶ Fazle API /auth/login (JWT)
  ├── /api/setup-status ──▶ Fazle API /auth/setup-status
  ├── /api/setup ──▶ Fazle API /auth/setup
  └── All /fazle/* proxied via JWT Bearer token
```

### 6.6 — Authentication Method

1. **Fazle UI**: NextAuth.js with CredentialsProvider → calls Fazle API `/auth/login` → gets JWT → stores in NextAuth session
2. **Fazle API**: Dual auth — API Key (X-API-Key header) or JWT (Authorization: Bearer)
3. **Dograh UI**: Built-in auth with `OSS_JWT_SECRET`
4. **JWT Duration**: 7 days (both NextAuth session and Fazle JWT)
5. **Password Hashing**: bcrypt via passlib

---

## STEP 7 — DOMAIN & NETWORKING

### 7.1 — Domains

| Domain | Purpose | Proxied To | SSL |
|--------|---------|------------|-----|
| iamazim.com | Dograh UI + API + Grafana | UI (3010), API (8000), Grafana (3030) | Let's Encrypt |
| api.iamazim.com | Dograh API (direct) | API (8000) | Let's Encrypt |
| livekit.iamazim.com | LiveKit WebRTC signaling | LiveKit (7880) | Let's Encrypt |
| fazle.iamazim.com | Fazle UI + API | UI (3020), API (8100) | Let's Encrypt |
| turn.iamazim.com | TURN/STUN server | Coturn (3478/5349) | Let's Encrypt |

All domains use a **single wildcard certificate** from `/etc/letsencrypt/live/iamazim.com/`.

### 7.2 — Nginx Reverse Proxy Configuration

**iamazim.com** routing:
```
/api/config/*     → dograh_ui (3010)    # Next.js internal routes
/api/auth/*       → dograh_ui (3010)    # Next.js auth routes
/api/*            → dograh_api (8000)   # Backend API (rate limited 30r/s)
/telephony/*      → dograh_api (8000)   # Twilio webhooks
/ws/*             → dograh_api (8000)   # WebSocket signaling
/grafana/*        → grafana (3030)      # IP-restricted monitoring
/*                → dograh_ui (3010)    # Frontend (default)
```

**fazle.iamazim.com** routing:
```
/api/fazle/*      → fazle_api (8100)    # Fazle API (rate limited 20r/s)
/health           → fazle_api (8100)    # Health check
/docs             → BLOCKED (404)       # API docs disabled
/openapi.json     → BLOCKED (404)       # OpenAPI spec disabled
/*                → fazle_ui (3020)     # Fazle dashboard (default)
```

### 7.3 — SSL Configuration

- Provider: Let's Encrypt (Certbot)
- Certificate path: `/etc/letsencrypt/live/iamazim.com/`
- HSTS: Enabled (max-age=31536000, includeSubDomains)
- HTTP → HTTPS redirect on all domains
- ACME challenge served from `/var/www/certbot`

### 7.4 — Direct Port Exposures (Not via Nginx)

| Port | Protocol | Service | Binding |
|------|----------|---------|---------|
| 7881 | TCP | LiveKit RTC | 0.0.0.0 (public) |
| 50000-50200 | UDP | LiveKit WebRTC media | 0.0.0.0 (public) |
| 3478 | TCP+UDP | Coturn STUN/TURN | 0.0.0.0 (public) |
| 5349 | TCP+UDP | Coturn TURN TLS | 0.0.0.0 (public) |
| 49152-49252 | UDP | Coturn relay | 0.0.0.0 (public) |

### 7.5 — Security Headers

Configured on iamazim.com and fazle.iamazim.com:
- X-Frame-Options: SAMEORIGIN
- X-Content-Type-Options: nosniff
- X-XSS-Protection: 1; mode=block
- Referrer-Policy: strict-origin-when-cross-origin
- Content-Security-Policy: Configured
- Strict-Transport-Security: max-age=31536000
- Permissions-Policy: microphone=(self), camera=(), geolocation=()

---

## STEP 8 — FILE STORAGE

### 8.1 — MinIO (S3-Compatible)

- **Container**: minio
- **Bucket**: `voice-audio`
- **Port**: 9000 (API), 9001 (Console)
- **Access**: Internal only (db-network)
- **Used By**: Dograh API (voice recordings)
- **CORS**: iamazim.com, fazle.iamazim.com

### 8.2 — Fazle File Upload

- **Endpoint**: POST `/fazle/files/upload`
- **Supported formats**: PDF, DOCX, TXT, PNG, JPG, JPEG, GIF
- **Max size**: 20MB
- **Storage**: Text extracted → ingested into Qdrant via memory service
- **No persistent file storage** — files are processed in-memory, text is vectorized, originals are NOT stored

### 8.3 — Other Storage

| Data | Store | Location |
|------|-------|----------|
| Voice audio | MinIO | `voice-audio` bucket |
| LLM models | Ollama volume | `ollama_data` |
| Vector memories | Qdrant volume | `qdrant_data` |
| Metrics history | Prometheus volume | `prometheus_data` (30d retention) |
| Logs | Loki volume | `loki_data` (14d retention) |
| Grafana dashboards | Grafana volume | `grafana_data` |

---

## STEP 9 — SECURITY REVIEW

### 9.1 — Credentials Analysis

| Finding | Severity | Detail |
|---------|----------|--------|
| `.env.local` in repo | HIGH | Contains generated (not production) secrets but is in `.gitignore`. Verify it's not committed. |
| `deployment-package/.env.secure` | HIGH | Potentially contains production secrets. Verify it's encrypted or gitignored. |
| `New VPS Password.txt` | CRITICAL | **Plaintext VPS password file in repo root.** Must be removed and password rotated. |
| OpenAI key placeholder | OK | `.env.local` has `sk-replace-with-real-openai-key` (placeholder). |
| Default database password | OK | `.env.example` has `CHANGE_ME_*` placeholders (templates only). |
| Fazle API key checked | OK | Uses `hmac.compare_digest()` for timing-safe comparison. |

### 9.2 — Port Exposure

| Port | Risk | Status |
|------|------|--------|
| 7881 (LiveKit RTC) | LOW | Required for WebRTC, protocol-specific |
| 3478/5349 (TURN) | LOW | Required for NAT traversal, auth-protected |
| 50000-50200/UDP | LOW | WebRTC media ports, protocol-specific |
| 49152-49252/UDP | LOW | TURN relay ports, auth-protected |
| All internal ports | OK | Bound to 127.0.0.1 or internal networks |

### 9.3 — Security Measures In Place

- **Network segmentation**: 4 networks (app, db, ai, monitoring)
- **Internal network isolation**: db-network, ai-network, monitoring-network are `internal: true`
- **Rate limiting**: Nginx rate limiting on API endpoints (30r/s API, 20r/s Fazle, 10r/s general)
- **Content Security Policy**: Configured on all domains
- **CORS**: Restricted to specific origins
- **Input validation**: Pydantic schemas with regex validation, max length limits, safe text checks
- **SSRF protection**: IP address validation on web scraping (blocks private/local IPs)
- **RLS**: PostgreSQL row-level security on user data
- **Read-only containers**: Fazle services use `read_only: true` with tmpfs
- **Resource limits**: All containers have CPU/memory limits
- **Log rotation**: All containers have json-file driver with max-size/max-file
- **Audit logging**: Append-only audit trail for admin operations
- **PII redaction**: Trainer service redacts email, phone, SSN, credit cards before storing
- **Content safety**: OpenAI Moderation API with child-safe thresholds
- **cAdvisor security**: `no-new-privileges:true` security opt

### 9.4 — Security Issues Found

| Issue | Severity | Detail |
|-------|----------|--------|
| `New VPS Password.txt` | **CRITICAL** | Plaintext VPS password in repo root. Must be deleted and password rotated. |
| All services use `postgres` superuser | **HIGH** | Role hardening SQL exists but is not applied. All services have full DB access. |
| Grafana IP restriction incomplete | MEDIUM | Only allows 127.0.0.1, ::1, and VPS IP. Admin needs to add their own IP for remote access. |
| API docs disabled but not removed | LOW | Fazle API has `docs_url=None, redoc_url=None`, and Nginx blocks `/docs`. Defense in depth is good. |
| Coturn runs as root | MEDIUM | `user: root` in docker-compose for TURN server (needed for cert access). |
| Docker socket mounted | MEDIUM | Promtail mounts `/var/run/docker.sock` (read-only, required for log collection). |

---

## STEP 10 — MIGRATION RISK REPORT

### Target Architecture

```
/home/azim/
├── ai-infra/                    # Shared infrastructure
│   └── docker-compose.yaml      # Postgres, Redis, MinIO, Qdrant, Ollama, monitoring
│
├── dograh/                      # Dograh voice agent platform
│   └── dograh-docker-compose.yaml  # Dograh API, UI, LiveKit, Coturn, Cloudflared
│
└── fazle-ai/                    # Fazle personal AI system
    └── fazle-docker-compose.yaml   # Fazle API, Brain, Memory, Tasks, Tools, Trainer, Voice, UI
```

### 10.1 — What Could Break During Migration

| Risk | Severity | Detail | Mitigation |
|------|----------|--------|------------|
| **Shared database splits** | CRITICAL | Both Dograh and Fazle use the SAME PostgreSQL instance and database (`postgres`). Splitting the compose means they must still connect to the same Postgres. | Keep Postgres in `ai-infra`. Both stacks connect via shared Docker network. |
| **Redis DB isolation** | HIGH | Redis is shared: DB 0 (Dograh/LiveKit), DB 1 (Brain), DB 2 (Trainer). If Redis moves to a different network, all services lose connectivity. | Keep Redis in `ai-infra` with cross-stack network access. |
| **Docker network changes** | HIGH | Current services depend on DNS resolution via Docker network aliases (e.g., `redis`, `postgres`, `fazle-brain`). Splitting compose files creates separate default networks. | Create a shared external network that all stacks join. |
| **Volume ownership** | HIGH | Named volumes (`postgres_data`, `redis_data`, etc.) are bound to a specific compose project. Moving to a different compose file may create new empty volumes. | Use explicit volume naming or migrate data. |
| **Service dependency chains** | MEDIUM | Fazle API depends on `fazle-brain` (service_healthy). Brain depends on `qdrant` and `ollama`. Cross-compose health checks don't work. | Remove cross-compose `depends_on`. Implement startup retries instead. |
| **Internal hostname resolution** | MEDIUM | Services reference each other by Docker service name (e.g., `http://fazle-brain:8200`). These names must remain the same across compose stacks. | Use container names + shared external network. |
| **Build context paths** | LOW | Fazle services build from `./fazle-system/api`. If the compose file moves to `/home/azim/fazle-ai/`, the build context path changes. | Update build contexts or pre-build images. |
| **Nginx proxy targets** | LOW | Nginx expects services on `127.0.0.1:XXXX`. Port bindings must not change. | Keep identical port bindings in new compose files. |
| **LiveKit ↔ Redis** | MEDIUM | LiveKit uses Redis for room coordination. If Redis moves to a different stack, LiveKit must join that network. | Ensure LiveKit has access to Redis via shared network. |
| **Coturn ↔ Cert volumes** | LOW | Coturn mounts Let's Encrypt certs from host path. This is host-dependent, not compose-dependent. | Works as-is regardless of compose layout. |

### 10.2 — Services That MUST Remain Unchanged

| Service | Reason |
|---------|--------|
| **Dograh API** | Pre-built image (`dograhai/dograh-api`). Cannot modify, only configure. Container name `dograh-api` may be referenced by Nginx and other services. |
| **Dograh UI** | Pre-built image (`dograhai/dograh-ui`). Cannot modify. |
| **PostgreSQL** | Single instance shared by both systems. Moving or renaming would break all data. |
| **Redis** | Shared across 3 subsystems with different DB numbers. |
| **LiveKit** | Uses specific port bindings (7880, 7881, 50000-50200) that cannot change. |
| **Coturn** | External TURN clients rely on fixed ports (3478, 5349). |

### 10.3 — Ports That CANNOT Change

| Port | Service | Reason |
|------|---------|--------|
| 80/443 | Nginx | HTTP/HTTPS standard ports |
| 8000 | Dograh API | Nginx proxies to 127.0.0.1:8000 |
| 3010 | Dograh UI | Nginx proxies to 127.0.0.1:3010 |
| 7880 | LiveKit HTTP | Nginx proxies to 127.0.0.1:7880 |
| 7881 | LiveKit RTC | Direct exposure (0.0.0.0) |
| 3478/5349 | Coturn | TURN protocol standard ports |
| 8100 | Fazle API | Nginx proxies to 127.0.0.1:8100 |
| 3020 | Fazle UI | Nginx proxies to 127.0.0.1:3020 |
| 3030 | Grafana | Nginx proxies to 127.0.0.1:3030 (mapped from 3000) |
| 50000-50200 | LiveKit UDP | WebRTC media ports (direct) |
| 49152-49252 | Coturn relay | TURN relay ports (direct) |

### 10.4 — Database Names That Must Stay the Same

| Database | Current Value | Used By |
|----------|---------------|---------|
| PostgreSQL DB | `postgres` | Dograh API, all Fazle services |
| PostgreSQL User | `postgres` | All services |
| Redis DB 0 | Default | Dograh, LiveKit |
| Redis DB 1 | `redis:6379/1` | Fazle Brain |
| Redis DB 2 | `redis:6379/2` | Fazle Trainer |
| Redis DB 3 | `redis:6379/3` | Fazle LLM Gateway (cache, rate limits, usage) |
| Redis DB 4 | `redis:6379/4` | Fazle Learning Engine (relationship graph) |
| Redis DB 5 | `redis:6379/5` | Fazle Queue + Workers (Redis Streams) |
| Qdrant Collection | `fazle_memories` | Fazle Memory |
| MinIO Bucket | `voice-audio` | Dograh API |

### 10.5 — API Endpoints That Must Not Change

| Endpoint | Domain | Consumer |
|----------|--------|----------|
| /api/v1/* | iamazim.com, api.iamazim.com | Dograh UI, Twilio, external clients |
| /telephony/* | iamazim.com | Twilio webhooks (configured externally) |
| /api/v1/livekit/webhook | Internal | LiveKit server |
| /fazle/decision | fazle-api:8100 | Dograh API (internal POST) |
| /api/fazle/* | fazle.iamazim.com | Fazle UI |
| /health | All services | Health checks, monitoring |
| /metrics | Fazle services | Prometheus scraping |

---

## STEP 11 — MIGRATION READINESS SCORE

### System Complexity: HIGH

- **30 services** in a single docker-compose.yaml (29 containers with worker replicas)
- **4 isolated networks** with careful service placement
- **Shared infrastructure** (single Postgres, single Redis with DB 0-5 isolation)
- **Cross-system integration** (Dograh ↔ Fazle via `/fazle/decision`)
- **LLM Gateway routing** (Brain + Trainer route through Gateway with fallback flag)
- **Async queue** (Redis Streams with consumer group workers)
- **Pre-built images** (Dograh API/UI cannot be modified)
- **12 custom Dockerfiles** for Fazle services
- **4 Nginx virtual hosts** with complex routing rules

### Migration Difficulty: MEDIUM-HIGH

| Factor | Rating | Notes |
|--------|--------|-------|
| Service decomposition | MEDIUM | Services are already microservices, but tightly coupled via shared DB |
| Data layer | HIGH | One Postgres, one Redis shared across all systems — hardest to split |
| Network reconfiguration | MEDIUM | Requires external networks for cross-compose communication |
| Volume migration | HIGH | Named volumes must be preserved or data is lost |
| Port bindings | LOW | Can keep identical port bindings in new setup |
| Nginx changes | NONE | Nginx runs on host, unchanged by compose reorganization |
| Build paths | LOW | Update relative paths in new compose files |
| Testing | MEDIUM | Need to verify all inter-service communication works across compose boundaries |

### Potential Risks Summary

| # | Risk | Probability | Impact | Mitigation |
|---|------|-------------|--------|------------|
| 1 | Data loss from volume mishandling | LOW | CRITICAL | Backup all volumes before migration. Use `docker volume inspect` to map volume locations. |
| 2 | Service DNS resolution failure | MEDIUM | HIGH | Use external named networks shared across compose files. |
| 3 | Health check dependency failures | MEDIUM | MEDIUM | Replace cross-compose `depends_on` with retry logic or startup ordering scripts. |
| 4 | Downtime during cutover | HIGH | MEDIUM | Plan for a maintenance window. Use `docker compose down && docker compose up` in sequence. |
| 5 | Redis data persistence | LOW | HIGH | Ensure Redis RDB/AOF is flushed before migration. |
| 6 | Dograh ↔ Fazle integration breaks | MEDIUM | HIGH | Verify `/fazle/decision` endpoint is reachable from Dograh API after migration. |

---

## FINAL SUMMARY

### Current System At-a-Glance

| Dimension | Current State |
|-----------|---------------|
| **Total Services** | 30 (in single docker-compose.yaml, 29 containers — workers ×2 replicas) |
| **Custom Services** | 12 (Fazle microservices, all Python 3.12 + FastAPI) |
| **Pre-built Services** | 2 (Dograh API + UI, from Docker registry) |
| **Infrastructure Services** | 6 (Postgres, Redis, MinIO, Qdrant, Ollama, Cloudflared) |
| **Monitoring Services** | 6 (Prometheus, Grafana, Loki, Promtail, Node Exporter, cAdvisor) |
| **WebRTC Services** | 2 (LiveKit, Coturn) |
| **AI Enhancement Services** | 4 (LLM Gateway, Learning Engine, Queue, Workers) |
| **UI Applications** | 2 (Dograh UI on 3010, Fazle UI on 3020) |
| **Database** | PostgreSQL 17 (pgvector), single instance, shared |
| **Cache** | Redis 8.0, single instance, DB 0/1/2/3/4/5 |
| **Vector DB** | Qdrant v1.17, collection: fazle_memories |
| **LLM** | OpenAI GPT-4o (primary via Gateway), Ollama qwen2.5:3b (fallback) |
| **Auth** | JWT (bcrypt), dual: API Key + JWT Bearer |
| **SSL** | Let's Encrypt, single wildcard cert |
| **Domains** | 5 (iamazim.com, api., livekit., fazle., turn.) |
| **Networks** | 4 Docker networks (app, db, ai, monitoring) |
| **Volumes** | 9 named Docker volumes |
| **API Endpoints** | 50+ across all services |
| **DB Tables** | 5+ Fazle tables + unknown Dograh tables |
| **Docker Compose Files** | 5 (1 main + 1 dograh-standalone + 3 three-stack + 1 backup) |
| **VPS** | Contabo 5.189.131.48, 4 CPUs AMD EPYC, 7.8GB RAM, 73GB disk (46% used) |
| **Docker** | v29.2.1, Docker Compose v5.1.0 |
| **OS** | Ubuntu Linux 5.15.0-171-generic |

### VPS Resource Usage (Post Phase 4+5 + Cleanup)

| Metric | Value |
|--------|-------|
| Disk usage | 34GB / 73GB (46%) — cleaned from 83% |
| RAM usage | ~5.8GB / 7.8GB |
| Docker images | 28 (26.4GB) — cleaned from 51 images (55.2GB) |
| Containers running | 29 (27 healthy + promtail + cloudflared) |
| Load average | ~4.08 (4 CPUs = at capacity) |

### Pre-Migration Checklist

Before starting any migration:

- [ ] **Backup all Docker volumes** (postgres_data, redis_data, qdrant_data, ollama_data, minio-data)
- [ ] **Export PostgreSQL dump** (`pg_dumpall`)
- [ ] **Document current container IPs** (`docker inspect`)
- [ ] **Remove `New VPS Password.txt`** from repo and rotate VPS password
- [ ] **Verify `.env.local` and `deployment-package/.env.secure` are gitignored**
- [ ] **Test health endpoints** for baseline before migration
- [ ] **Plan maintenance window** for downtime during cutover
- [ ] **Create external Docker network** for cross-compose communication
- [ ] **Decide on database separation strategy** (shared vs. split)

---

*This report reflects the production state as of 2026-03-15, including Phase 4 (LLM Gateway + Learning Engine) and Phase 5 (Async Queue + Workers) deployments. It serves as the baseline blueprint for the system architecture.*
