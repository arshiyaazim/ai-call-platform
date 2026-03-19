# Level-2 Autonomous DevOps AI Agent — Full Audit Report

**Date:** 2026-03-17  
**Target:** `azim@5.189.131.48` (`vmi3117764`)  
**Project:** `/home/azim/ai-call-platform/`  
**Agent Phases Completed:** 1–10 (Data Collection & Analysis)

---

## 1. System Overview

| Parameter | Value |
|-----------|-------|
| OS | Ubuntu 22.04.5 LTS (Jammy) |
| Kernel | Linux (x86_64) |
| CPUs | 4 |
| RAM | 8 GB |
| Disk | 73 GB total, 60 GB used (**83% full**) |
| Swap | 3 GB (1.9 GB used, swappiness=10) |
| Uptime | 13 days (booted 2026-03-03) |
| Docker | 29.2.1, Compose v5.1.0 |
| Containers | 29 running, all healthy |

### Security Posture
- **SSH:** Root login disabled, password auth disabled, pubkey only — ✅ Hardened
- **Failed SSH logins (24h):** 0
- **Docker socket:** `root:docker` (660) — ✅ Correct
- **`.env` permissions:** 600 — ✅ Correct
- **Unattended upgrades:** Installed and active — ✅
- **SSL certificate:** Valid until Jun 6, 2026 — ✅
- **Firewall (UFW):** Not enabled — ⚠️ INFO (Docker manages iptables directly)

### Cron Jobs
| Schedule | Job |
|----------|-----|
| 03:00 daily | `/home/azim/ai-call-platform/scripts/backup.sh` |
| 03:00 daily | `certbot renew --quiet` |

### Listening Ports (External)
| Port | Service |
|------|---------|
| 22 | SSH |
| 80/443 | Nginx (HTTP/HTTPS) |
| 3478/5349 | Coturn (TURN/TURNS) |
| 7881 | LiveKit (WebRTC) |

All application ports (3010, 3020, 3030, 7880, 8000, 8101) bind to **127.0.0.1 only** — ✅ Correct

---

## 2. Architecture — Three-Stack Design

```
┌─────────────────────────────────────────────────────────────────┐
│                         NGINX (SSL)                             │
│  iamazim.com → dograh    fazle.iamazim.com → fazle             │
│  api.iamazim.com → dograh-api   livekit.iamazim.com → livekit  │
└────────────┬──────────────────┬──────────────────┬──────────────┘
             │                  │                  │
    ┌────────▼────────┐ ┌──────▼───────┐ ┌────────▼────────┐
    │  dograh/ stack   │ │ fazle-ai/    │ │  ai-infra/      │
    │                  │ │   stack      │ │    stack         │
    │ dograh-api       │ │ fazle-api    │ │ postgres         │
    │ dograh-ui        │ │ fazle-brain  │ │ redis            │
    │ livekit          │ │ fazle-memory │ │ qdrant           │
    │ coturn           │ │ fazle-voice  │ │ minio            │
    │ cloudflared      │ │ fazle-ui     │ │ ollama           │
    └──────────────────┘ │ +7 services  │ │ prometheus       │
                         └──────────────┘ │ grafana/loki     │
                                          │ promtail/cadvisor│
                                          │ node-exporter    │
                                          └──────────────────┘
    Shared external networks: app-network, db-network, ai-network
```

**Intended:** Three separate compose files (`ai-infra/`, `fazle-ai/`, `dograh/`) with shared external networks.  
**Actual:** Mixed — some containers run from root `docker-compose.yaml` (legacy), creating split ownership.

---

## 3. Container Inventory (29 Running)

### Fazle AI Stack (12 containers)
| Container | Image | CPU | Memory | Compose Project |
|-----------|-------|-----|--------|----------------|
| fazle-api-blue | fazle-api:latest | ~1% | ~120 MB | **N/A (orphaned)** |
| fazle-brain | fazle-brain:latest | ~0% | ~80 MB | fazle-ai |
| fazle-memory | fazle-memory:latest | ~0% | ~500 MB | fazle-ai |
| fazle-voice | fazle-voice:latest | ~0% | 626 MB/1 GB | fazle-ai |
| fazle-ui | fazle-ui:latest | ~0% | ~70 MB | fazle-ai |
| fazle-llm-gateway | fazle-llm-gateway:latest | ~0% | ~80 MB | fazle-ai |
| fazle-learning-engine | fazle-learning-engine:latest | ~0% | ~80 MB | fazle-ai |
| fazle-task-engine | fazle-task-engine:latest | ~0% | ~80 MB | **ai-call-platform** |
| fazle-trainer | fazle-trainer:latest | ~0% | ~80 MB | **ai-call-platform** |
| fazle-queue | fazle-queue:latest | ~0% | ~60 MB | **ai-call-platform** |
| fazle-workers (x2) | fazle-workers:latest | ~0% | ~80 MB ea | **ai-call-platform** |
| fazle-web-intelligence | fazle-web-intelligence:latest | ~0% | ~80 MB | **N/A (orphaned)** |

### Dograh Stack (5 containers)
| Container | Compose Project |
|-----------|----------------|
| dograh-api | **ai-call-platform** |
| dograh-ui | **ai-call-platform** |
| livekit | **ai-call-platform** |
| coturn | **ai-call-platform** |
| cloudflared | **ai-call-platform** |

### AI Infrastructure Stack (12 containers)
| Container | Compose Project |
|-----------|----------------|
| postgres | **ai-call-platform** |
| redis | **ai-call-platform** |
| qdrant | **ai-call-platform** |
| minio | **ai-call-platform** |
| ollama | **ai-call-platform** |
| prometheus | **ai-call-platform** |
| grafana | **ai-call-platform** |
| loki | **ai-call-platform** |
| promtail | **ai-call-platform** |
| cadvisor | **ai-call-platform** |
| node-exporter | **ai-call-platform** |

---

## 4. Detected Problems

### PROBLEM #1 — CRITICAL: Mixed Compose Project Ownership
**Risk:** High — `docker compose down` in any stack may leave orphans or fail to manage related containers. Rolling updates will not work reliably.

**Current state:**
- Only 6 containers belong to the `fazle-ai` project (via `fazle-ai/docker-compose.yaml`)
- 21 containers belong to the `ai-call-platform` project (via root `docker-compose.yaml`)
- 2 containers have NO compose project labels (manually created / orphaned)

**Root cause:** The root `docker-compose.yaml` (legacy monolithic file) was used to start container infrastructure, dograh, and some fazle services. Later, `fazle-ai/docker-compose.yaml` was introduced for blue-green deployment, but not all fazle services were migrated to it.

**Impact:** 
- `cd fazle-ai && docker compose down` only stops 6 of 12 fazle services
- `cd dograh && docker compose down` stops 0 dograh containers (they belong to root project)
- Root compose `down` would nuke everything including infrastructure

---

### PROBLEM #2 — CRITICAL: Disk Usage at 83%
**Risk:** High — Docker builds may fail, logs may fill up, database writes may fail.

| Category | Size | Reclaimable |
|----------|------|-------------|
| Docker images | 53.9 GB | 31 GB (57%) |
| Build cache | 2.14 GB | 897 MB |
| Volumes | 7.3 GB | 0 B |
| Containers | 35 MB | 0 B |

**Reclaimable items:**
- 1 dangling image: **12.4 GB** (`d7c9a095dc24`)
- Old rolling deployment images:
  - `fazle-memory:rolling-20260313_235603` — 12.4 GB
  - `fazle-api:rolling-20260313_234726` — 331 MB
  - `fazle-web-intelligence:rolling-20260314_001810` — 249 MB
  - Multiple older `fazle-api` rolling tags (5 total)
- Build cache: 897 MB reclaimable

**Estimated recoverable:** ~25-31 GB

---

### PROBLEM #3 — HIGH: fazle-voice TypeError
**Risk:** Medium-High — Voice agent may not process calls correctly.

```
TypeError: Can't instantiate abstract class _SingleResponseStream 
without an implementation for abstract method '_run'
```

**Root cause:** `livekit-agents==0.12.20` with `livekit-plugins-openai==0.10.14` — version incompatibility between the agent framework and the OpenAI plugin. The internal API changed (abstract method `_run` added) but the plugin version doesn't implement it.

**Impact:** Voice streaming responses may fail when attempting to use OpenAI TTS/STT through LiveKit.

---

### PROBLEM #4 — MEDIUM: fazle-api bcrypt Warning
**Risk:** Low-Medium — Warning only, auth still works, but may break on bcrypt update.

```
AttributeError: module 'bcrypt' has no attribute '__about__'
```

**Root cause:** `passlib[bcrypt]==1.7.4` + `bcrypt==4.2.1`. Passlib tries to read `bcrypt.__about__.__version__` which was removed in bcrypt 4.x.

**Fix:** Pin `bcrypt==4.0.1` in `fazle-system/api/requirements.txt`, or upgrade to `passlib==1.7.5+` (if available).

---

### PROBLEM #5 — MEDIUM: Orphaned Docker Resources

| Resource Type | Name/ID | Details |
|---------------|---------|---------|
| Volume | `d3c9b093270c...` | Anonymous orphaned volume |
| Volume | `ollama_data` | Duplicate — `ai-call-platform_ollama_data` also exists (active) |
| Network | `ai-call-platform_app-network` | Zero containers attached (orphaned) |

**Risk:** Low-Medium — Wastes disk space, confuses resource audits.

---

### PROBLEM #6 — LOW: LiveKit Historical Restarts
**Status:** LiveKit container has 8 historical restarts but has been stable for 5+ days with active WebRTC sessions.

**Risk:** Low — Self-recovered. Monitor only.

---

### PROBLEM #7 — LOW: fazle-memory Image Bloat (12.4 GB)
**Root cause:** `sentence-transformers==3.3.1` pulls full PyTorch (~2 GB) + transformer models. The resulting image is 12.4 GB.

**Risk:** Low — Functional but inflates disk usage and slows deployment. Not a bug.

**Future optimization:** Use `torch-cpu` variant or pre-download model to separate volume.

---

### PROBLEM #8 — INFO: Swap Pressure
1.9 GB of 3 GB swap in use. `vm.swappiness=10` is correctly configured.

**Risk:** Low — Normal for 8 GB RAM with 29 containers. System is not thrashing.

---

## 5. Service Health Summary

| Service | Health | DNS Resolution | HTTP Status |
|---------|--------|---------------|-------------|
| fazle-api (blue) | ✅ Healthy | ✅ | 200 OK |
| fazle-brain | ✅ Healthy | ✅ | 200 OK |
| fazle-memory | ✅ Healthy | ✅ | 200 OK |
| fazle-voice | ✅ Healthy | ✅ | 200 OK |
| fazle-ui | ✅ Healthy | ✅ | 200 OK |
| fazle-llm-gateway | ✅ Healthy | ✅ | 200 OK |
| fazle-learning-engine | ✅ Healthy | ✅ | 200 OK |
| fazle-task-engine | ✅ Healthy | ✅ | 200 OK |
| fazle-web-intelligence | ✅ Healthy | ✅ | 200 OK |
| dograh-api | ✅ Healthy | ✅ | 200 OK |
| dograh-ui | ✅ Healthy | ✅ | 200 OK |
| postgres | ✅ Healthy | ✅ | N/A |
| redis | ✅ Healthy | ✅ | N/A |
| qdrant | ✅ Healthy | ✅ | 200 OK |
| minio | ✅ Healthy | ✅ | 200 OK |

---

## 6. Database Health

| Database | Status | Size | Notes |
|----------|--------|------|-------|
| PostgreSQL | ✅ Healthy | 12 MB | pgvector enabled, 8 tables |
| Redis | ✅ Healthy | 1.92 MB memory | 8 databases, pub/sub active |
| Qdrant | ✅ Healthy | — | Vector collections operational |
| MinIO | ✅ Healthy | — | Object storage, S3-compatible |

---

## 7. SSL & Reverse Proxy

- **SSL Certificate:** Valid, expires **Jun 6, 2026** (81 days remaining)
- **Auto-renewal:** Certbot cron active at 03:00 daily
- **Nginx:** Syntax OK, 4 server blocks active, all upstreams responding
- **Blue-green:** API upstream at `/etc/nginx/upstreams/fazle-api.conf` → `127.0.0.1:8101` (blue active)

---

## 8. Proposed Repair Plan

### Phase 12 — Disk Cleanup (SAFE, non-destructive)
1. Remove dangling image (`docker image prune`)
2. Remove old rolling deployment images (keep only `:latest` tags)
3. Prune unused build cache (`docker builder prune`)
4. Remove orphaned anonymous volume
5. Remove orphaned network `ai-call-platform_app-network`
6. **Expected recovery: ~25-31 GB → disk down to ~40-45%**

### Phase 13 — Compose Project Unification
1. Stop containers that belong to root `ai-call-platform` project but should belong to their respective stacks
2. Restart them through the correct compose files (`dograh/`, `ai-infra/`, `fazle-ai/`)
3. Verify all containers have correct project labels
4. **Risk:** Brief service interruption (few seconds per service during restart)

### Phase 14 — Dependency Fixes
1. Fix `bcrypt` version in `fazle-system/api/requirements.txt` — pin `bcrypt==4.0.1`
2. Fix `livekit-plugins-openai` version in `fazle-system/voice/requirements.txt` — upgrade to compatible version
3. Rebuild affected images and redeploy
4. **Risk:** Service restart required for fazle-api and fazle-voice

### Phase 15 — Cleanup Duplicate Resources
1. Remove duplicate `ollama_data` volume (standalone, not compose-managed)
2. Verify no data loss (compose-managed `ai-call-platform_ollama_data` is the active one)

### Phase 16 — Verification
1. Run full health checks on all 29 containers
2. Verify DNS resolution across all services
3. Verify HTTP endpoints
4. Check error logs for resolved issues
5. Confirm disk usage improvement

### Phase 17 — Final Report
Generate post-repair report with before/after comparisons.

---

## 9. What Will NOT Be Changed
- No new features or services will be added
- No configuration changes beyond fixing identified problems
- No database schema modifications
- No SSL/domain changes
- No firewall rule changes
- No Nginx config changes (currently correct)
- No backup schedule changes

---

## ⚡ ACTION REQUIRED

**Please review this audit report and reply with approval to proceed with repairs.**

You may approve:
- **All phases** (12-17) — Full repair
- **Specific phases only** — e.g., "Phase 12 only" for disk cleanup
- **Skip specific items** — e.g., "All except Phase 14"
- **Reject** — No changes, report only

**Priority recommendation:** Start with **Phase 12 (Disk Cleanup)** — it's the most urgent (83% disk), completely safe, and recovers ~25-31 GB immediately.
