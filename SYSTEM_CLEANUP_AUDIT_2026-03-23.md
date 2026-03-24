# 🔍 COMPLETE SYSTEM AUDIT + CLEANUP + MERGE PLAN
**Date:** 2026-03-23 | **Scope:** Local workspace + VPS architecture | **Priority:** CLEAN, MINIMAL, PRODUCTION-READY

---

## 📋 EXECUTIVE SUMMARY

| Metric | Count |
|--------|-------|
| Total root-level files | 25 |
| Files to **DELETE** | 12 |
| Files to **MERGE** | 8 → 3 |
| Files to **KEEP** | 13 |
| Scripts total (scripts/) | 80+ |
| Scripts to **DELETE** | 16 |
| Scripts to **ARCHIVE** | 14 |
| Docker Compose files | 7 (only 3 needed) |
| Env vars total | 66 |
| Env vars ✅ Set | 24 |
| Env vars ❌ Missing/Placeholder | 16 |
| 🚨 **Security critical** | **2 files with plaintext secrets in repo** |
| Missing production features | 5 (escalation, business hours, DND, live agent, scheduled executor) |

### System Health Verdict: **BLOATED — Needs aggressive cleanup**
- 22 markdown reports at root (most are stale/duplicate)
- 7 docker-compose files serving the same 3-stack architecture
- 80+ scripts with ~30 duplicates or one-time-use leftovers
- PII data file (contacts.csv) in repo
- Plaintext API credentials committed to git

---

## 📊 PHASE 1 — FULL SYSTEM AUDIT

### 1. Architecture Overview

**Three-stack Docker deployment** on VPS `5.189.131.48` (iamazim.com):

| Stack | Compose File | Services | Deploy Order |
|-------|-------------|----------|-------------|
| **ai-infra** | `ai-infra/docker-compose.yaml` | 14 (Postgres, Redis, MinIO, Qdrant, Ollama, LiveKit, Coturn, Cloudflared, Prometheus, Grafana, Loki, Promtail, cAdvisor, Node Exporter) | 1st |
| **dograh** | `dograh/dograh-docker-compose.yaml` | 5 (API, UI, LiveKit, Coturn, Cloudflared) | 2nd |
| **fazle-ai** | `fazle-ai/docker-compose.yaml` | 20+ (API, Brain, Memory, Voice, Tasks, Trainer, LLM-GW, Learning, Queue, Workers×2, Autonomy, Tool, Knowledge Graph, Runner, Self-Learning, Guardrail, Workflow, Social, OTel) | 3rd |

**⚠️ CRITICAL BUG: LiveKit/Coturn defined in BOTH ai-infra AND dograh stacks — port conflict if both run.**
**Decision needed:** Keep LiveKit/Coturn in ONE stack only (recommendation: ai-infra only, use `dograh/docker-compose.yaml` without LiveKit).

---

### 2. File Duplication Analysis

#### Docker Compose Files (7 total → 3 needed)

| File | Purpose | Verdict |
|------|---------|---------|
| `ai-infra/docker-compose.yaml` | Infrastructure stack | ✅ **KEEP** |
| `dograh/docker-compose.yaml` | Dograh API+UI only (no LiveKit) | ✅ **KEEP** (use this if LiveKit in ai-infra) |
| `fazle-ai/docker-compose.yaml` | Fazle AI full stack (Phase 5+) | ✅ **KEEP** |
| `docker-compose.yaml` (root) | **LEGACY monolithic** — pre-Phase-6, missing 9 services | 🗑️ **DELETE** |
| `dograh-docker-compose.yaml` (root) | **LEGACY standalone** with own DB/Redis | 🗑️ **DELETE** |
| `dograh/dograh-docker-compose.yaml` | Dograh with LiveKit/Coturn (conflicts with ai-infra) | ⚠️ **ARCHIVE** (keep only if splitting LiveKit to Dograh) |
| `fazle-ai/fazle-docker-compose.yaml` | **LEGACY** Fazle without Phase 5 | 🗑️ **DELETE** |

#### Root-Level Markdown Reports (22 → 5)

| File | Purpose | Verdict |
|------|---------|---------|
| `README.md` | Primary project documentation | ✅ **KEEP** — merge ops content from `production_readme.md` |
| `UPGRADE_ROADMAP.md` | Active roadmap with checked items | ✅ **KEEP** |
| `zero-downtime-deploy.md` | Deployment procedure | ✅ **KEEP** |
| `migration-checklist.md` | Three-stack migration checklist | ✅ **KEEP** (still useful as reference) |
| `Features_new_deploy.txt` | Dashboard feature catalog | ✅ **KEEP** |
| `production_readme.md` | Ops-focused README duplicate | 🔀 **MERGE** into README.md |
| `AUDIT_REPORT.md` | Mar 7 — superseded | 🗑️ **DELETE** |
| `AUDIT_REPORT_2026-03-10.md` | Mar 10 — overlaps INFRASTRUCTURE | 🗑️ **DELETE** |
| `INFRASTRUCTURE_AUDIT_REPORT.md` | Same audit, different angle | 🗑️ **DELETE** |
| `SYSTEM_AUDIT_REPORT.md` | Structure audit — covered by this report | 🗑️ **DELETE** |
| `GITOPS_AUDIT_REPORT_2026-03-18.md` | Single snapshot | 🗑️ **DELETE** |
| `PHASE11_AUDIT_REPORT.md` | Phase 11 audit | 🗑️ **DELETE** |
| `PHASE11_REMEDIATION_REPORT.md` | Phase 11 remediation | 🗑️ **DELETE** |
| `PHASE4_5_DEPLOYMENT_REPORT.md` | Phase 4-5 deployment | 🗑️ **DELETE** |
| `PHASE5_DEPLOYMENT_REPORT.md` | Phase 5 deployment | 🗑️ **DELETE** |
| `AI_WATCHDOG_DEPLOYMENT_REPORT.md` | Watchdog deployment | 🗑️ **DELETE** |
| `DASHBOARD_DEPLOYMENT_REPORT.md` | Dashboard deployment | 🗑️ **DELETE** |
| `DEPLOYMENT_MANIFEST.md` | Mar 11 manifest | 🗑️ **DELETE** |
| `PRE_DEPLOY_CHECKLIST.md` | Duplicate of manifest | 🗑️ **DELETE** |
| `LOCAL_REMEDIATION_REPORT.md` | Old remediation | 🗑️ **DELETE** |
| `VERIFICATION_REPORT.md` | Old verification | 🗑️ **DELETE** |
| `as on 22032026.txt` | **🚨 PLAINTEXT SECRETS** | 🗑️ **DELETE IMMEDIATELY** + rotate all tokens |
| `contacts.csv` | **🚨 PII DATA** — personal contacts dump | 🗑️ **DELETE IMMEDIATELY** |

#### Root-Level Scripts & Tests

| File | Verdict |
|------|---------|
| `gen-secrets.sh` | Stub redirecting to `scripts/gen-secrets.sh` → 🗑️ **DELETE** |
| `migration-deploy.sh` | One-time migration script → ⚠️ **ARCHIVE** |
| `verify-remediation.sh` | Post-remediation check → ⚠️ **ARCHIVE** |
| `test_login.py` | Duplicate of test_login2.py → 🗑️ **DELETE** |
| `test_login2.py` | Manual login test → ✅ **KEEP** (rename to `test_login.py`) |
| `pytest.ini` | Pytest config → ✅ **KEEP** |

#### Monitoring/Observability Directories (merge into one)

| Path | Verdict |
|------|---------|
| `monitoring/dashboards/` | Contains 2 JSON dashboards | 🔀 **MERGE** all into `configs/grafana/dashboards/` |
| `monitoring/grafana/dashboards/` | Contains 3 JSON dashboards (1 duplicate of above) | 🔀 **MERGE** |
| `monitoring/grafana/provisioning/` | **EMPTY directories** | 🗑️ **DELETE** |
| `observability/grafana/dashboards/` | Contains 3 Phase-5 dashboards | 🔀 **MERGE** |

**Target:** All dashboards in `configs/grafana/dashboards/`. Delete `monitoring/` and `observability/` after merging.

---

### 3. Scripts Audit (scripts/)

#### DELETE (16 scripts — duplicates/one-time fixes)

| Script | Reason |
|--------|--------|
| `ollama-keepalive.sh` | Replaced by Ollama KEEP_ALIVE setting |
| `deploy-api-blue.sh` | Superseded by `deploy-api-blue-v2.sh` |
| `test-auth.sh` | Duplicate of `test-login.sh` |
| `test-multimodal.sh` | Superseded by `test-multimodal-v2.sh` |
| `check-projects.sh` | Overlaps `check-labels.sh` |
| `verify-dashboard.sh` | Superseded by `verify-dashboard-v2.sh` |
| `bench_warm.py` | Variation of `bench_ttfb.py` |
| `bench_clean.py` | Variation of `bench_ttfb.py` |
| `test-brain-health.py` | Trivial one-liner |
| `test-api-dns.py` | Duplicate of JS version |
| `test-api-dns.js` | Keep one or the other |
| `test_brain_perf.py` | Overlaps bench scripts |
| `check-livekit-api.py` | Dev-time inspection tool |
| `fix_interval.py` | One-time VPS typo fix |
| `fix_learning.py` | One-time VPS fix |
| `fix_learning2.py` | One-time VPS fix |

#### ARCHIVE (14 scripts → move to `scripts/archive/`)

| Script | Reason |
|--------|--------|
| `deploy.sh` | Monolithic deploy (replaced by three-stack) |
| `deploy-phase6.sh` | One-time migration |
| `rollback-phase6.sh` | One-time migration rollback |
| `phase0-snapshot.sh` | Emergency rollback snapshot |
| `phase1-disk-cleanup.sh` | One-time disk cleanup |
| `phase3-prep.sh` | One-time compose prep |
| `phase3-migrate.sh` | One-time migration |
| `phase3-migrate-fazle.sh` | One-time Fazle migration |
| `phase3-fix-volumes.sh` | One-time volume fix |
| `phase6-verify.sh` | One-time verification |
| `sudo-fix.sh` | One-time root fix |
| `activate-vision.sh` | One-time feature activation |
| `final-verify.sh` | One-time verification curls |
| `patch_phase5_settings.py` | One-time deploy patch |

#### MERGE (2 groups)

| Merge | Target |
|-------|--------|
| `rollback.sh` + `rollback-vps.sh` | → `rollback.sh` |
| `debug.sh` + `diagnose.sh` | → `diagnose.sh` |

#### KEEP (remaining ~30 scripts)

Core operational scripts: `deploy-to-vps.sh`, `deploy-rolling.sh`, `deploy-fazle-v2.sh`, `deploy-api-blue-v2.sh`, `gitops-deploy.sh`, `stack-up.sh`, `stack-down.sh`, `stack-status.sh`, `rollback-rolling.sh`, `health-check.sh`, `health-check-local.sh`, `diagnose.sh`, `docker-cleanup.sh`, `backup.sh`, `gen-secrets.sh`, `setup-firewall.sh`, `setup-minio-bucket.sh`, `setup-ollama.sh`, `setup-ssl.sh`, `sudo-setup.sh`, `create-networks.sh`, `coturn-entrypoint.sh`, `livekit-entrypoint.sh`, `ui-entrypoint.sh`, `db-migrate.sh`, `seed-family.py`, `set-persona-overrides.py`, `load-test.py`, `bench_final.py`, `bench_latency.py`, `test_v2_endpoints.py`, `swap-to-blue.sh`, all `vps/` scripts, and all test scripts not listed for deletion.

---

### 4. Environment Variables Audit

#### 🚨 BLOCKING — Must fix before production

| Variable | Status | Impact |
|----------|--------|--------|
| `FAZLE_JWT_SECRET` | ❌ **MISSING** from .env | Fazle API + UI **will crash on startup** |
| `OPENAI_API_KEY` | ⚠️ Placeholder | No GPT-4o; Brain/Memory/Voice fall back to Ollama |
| `SERPER_API_KEY` | ⚠️ Placeholder | Web search will fail silently |
| `SOCIAL_WHATSAPP_API_TOKEN` | ❌ Missing | WhatsApp send/receive disabled |
| `SOCIAL_WHATSAPP_PHONE_NUMBER_ID` | ❌ Missing | WhatsApp disabled |
| `SOCIAL_FACEBOOK_PAGE_ACCESS_TOKEN` | ❌ Missing | Facebook posting disabled |
| `SOCIAL_FACEBOOK_PAGE_ID` | ❌ Missing | Facebook disabled |
| `SOCIAL_ENCRYPTION_KEY` | ❌ Missing | Credentials stored unencrypted |
| `SOCIAL_VERIFY_TOKEN` | 🔵 Default `fazle-social-verify-2024` | Predictable — should be randomized |

#### ✅ Set and working (24 vars)

`POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `LIVEKIT_WS_URL`, `OSS_JWT_SECRET`, `FAZLE_API_KEY`, `TURN_SECRET`, `GRAFANA_PASSWORD`, `VPS_IP`, `BACKEND_API_ENDPOINT`, all LLM model/provider defaults, voice config defaults.

#### Complete Variable Table

| Category | Total | ✅ Set | ⚠️ Placeholder | ❌ Missing | 🔵 Default |
|----------|-------|-------|----------------|-----------|-----------|
| Meta/WhatsApp/Facebook | 6 | 0 | 0 | **6** | 0 |
| OpenAI/AI | 11 | 3 | **1** | 0 | 7 |
| Database | 3 | 3 | 0 | 0 | 0 |
| Redis | 1 | 1 | 0 | 0 | 0 |
| MinIO | 2 | 2 | 0 | 0 | 0 |
| LiveKit | 5 | 4 | 0 | 0 | 1 |
| Security | 5 | 3 | 0 | **2** | 0 |
| Monitoring | 2 | 2 | 0 | 0 | 0 |
| CORS/Domain | 6 | 3 | 0 | 0 | 3 |
| Voice | 9 | 0 | 0 | 0 | 9 |
| Web Search | 3 | 1 | **1** | **1** | 0 |
| Other | 7 | 2 | 0 | 0 | 5 |
| **TOTAL** | **60** | **24** | **2** | **9** | **25** |

---

### 5. Social Integration Status

| Platform | Code Status | Functional? | Blocker |
|----------|------------|-------------|---------|
| **WhatsApp Business API** | ✅ Complete — send, receive, template, broadcast, scheduling, webhook, AI auto-reply | ❌ **NOT FUNCTIONAL** | Missing: `SOCIAL_WHATSAPP_API_TOKEN`, `SOCIAL_WHATSAPP_PHONE_NUMBER_ID` |
| **Facebook Page API** | ✅ Complete — post, comment reply, react, webhook, content fetch | ❌ **NOT FUNCTIONAL** | Missing: `SOCIAL_FACEBOOK_PAGE_ACCESS_TOKEN`, `SOCIAL_FACEBOOK_PAGE_ID` |
| **Workflow triggers** | ✅ Fires `whatsapp.message.received`, `facebook.comment.received` events to workflow engine | ⚠️ Partially — workflow engine has no schedule executor | — |
| **Contact management** | ✅ Full CRUD with deduplication | ⚠️ Empty database | — |
| **Secret encryption** | ✅ Fernet-based encrypt/decrypt | ⚠️ Needs `SOCIAL_ENCRYPTION_KEY` | — |

---

### 6. Webhook System Audit

| Check | Status | Detail |
|-------|--------|--------|
| WhatsApp webhook GET (verification) | ✅ Implemented | `verify_token` query param check |
| WhatsApp webhook POST (receive) | ✅ Implemented | Delegates to `handle_whatsapp_webhook()` |
| Facebook webhook GET (verification) | ✅ Implemented | `verify_token` query param check |
| Facebook webhook POST (receive) | ✅ Implemented | Delegates to `handle_facebook_webhook()` |
| **HMAC signature validation** | ❌ **MISSING** | `X-Hub-Signature-256` NOT verified — anyone can POST fake payloads |
| API Gateway proxy (public webhook) | ✅ Implemented | `/fazle/social/whatsapp/webhook` and `/fazle/social/facebook/webhook` — no auth required (correct for Meta) |
| Meta App verification flow | ⚠️ Ready but untested | Token defaults to `fazle-social-verify-2024` — should be randomized |

**🚨 SECURITY GAP: Webhook POST endpoints do not validate X-Hub-Signature-256 from Meta. This means any HTTP client can inject fake messages. Must add HMAC verification before production.**

---

### 7. AI Brain Audit

| Component | Status | Detail |
|-----------|--------|--------|
| OpenAI GPT-4o | ✅ Code complete | Requires `OPENAI_API_KEY` (currently placeholder) |
| Ollama fallback | ✅ Working | `qwen2.5:0.5b` for fast, `qwen2.5:3b` for full |
| LLM Gateway routing | ✅ Working | Cache (300s), rate limit (10 rps), batch (75ms/4), fallback |
| Personality loading | ✅ Working | Per-user relationship-aware prompts via `persona_engine.py` |
| Memory retrieval | ✅ Working | Text + multimodal from Qdrant |
| Content safety | ✅ Working | OpenAI Moderation API, fail-closed for children |
| Multi-agent system | ✅ Working | 5 agents, smart routing (FAST_VOICE, CONVERSATION, FULL_PIPELINE) |
| Streaming | ✅ Working | SSE endpoints for voice TTS |

**Verdict: Brain is WORKING. Ollama-only mode active due to missing OpenAI key.**

---

### 8. Voice System Audit

| Component | Status | Detail |
|-----------|--------|--------|
| LiveKit WebRTC | ✅ Working | Full `VoicePipelineAgent` pipeline |
| OpenAI Whisper STT | ✅ Working | Requires `OPENAI_API_KEY` |
| Piper TTS (local) | ⚠️ Broken | `/models` volume NOT mounted in current compose; ONNX model missing |
| OpenAI TTS (remote) | ✅ Working | Voice `alloy`, requires `OPENAI_API_KEY` |
| ElevenLabs TTS | ❌ **NOT IMPLEMENTED** | No code exists anywhere |
| Smart query routing | ✅ Working | Simple → `/chat/fast`, complex → `/chat/agent/stream` |
| TTFB performance | ✅ Good | 131-367ms (P50: 207ms) under 400ms target |

**Verdict: Voice WORKS with OpenAI TTS. Piper local TTS is broken (missing model mount). ElevenLabs absent.**

---

### 9. Automation & Workflow Engine Audit

| Component | Status | Detail |
|-----------|--------|--------|
| Step types | ✅ 5 types | `llm_call`, `tool_call`, `condition`, `delay`, `webhook` |
| Trigger types | ⚠️ Partial | `manual` works; `schedule` and `event` are **cosmetic only** (no executor) |
| DB storage | ✅ Working | PostgreSQL tables for workflows + logs |
| Variable substitution | ✅ Working | `{{variable}}` in prompts |
| Condition logic | ⚠️ Basic | Only `truthy` and exact value match |
| **Schedule executor** | ❌ **MISSING** | No background job fires scheduled workflows |
| **Event listener** | ❌ **MISSING** | No inbound webhook for event triggers |
| **CORS** | ⚠️ Wide open | `allow_origins=["*"]` — should be restricted |
| **Authentication** | ❌ **MISSING** | No auth on any endpoint |

---

### 10. Missing Production Features

| Feature | Status | Location |
|---------|--------|----------|
| **Human escalation** | ❌ NOT IMPLEMENTED | Zero code anywhere — AI always auto-responds |
| **Business hours** | ❌ NOT IMPLEMENTED | No time-of-day awareness |
| **Do-not-disturb** | ❌ NOT IMPLEMENTED | No way to silence the bot |
| **Live agent queue** | ❌ NOT IMPLEMENTED | No human takeover capability |
| **Scheduled message executor** | ❌ NOT IMPLEMENTED | Messages saved to DB but never sent |
| **Auto social posting** | ❌ NOT IMPLEMENTED | Posts saved to DB but no cron fires them |
| **Reminder push to social** | ⚠️ PARTIAL | Brain creates reminders via task engine, but no push to WhatsApp |
| **Password reset email** | ⚠️ STUB | Token generated but email NOT sent |
| **Guardrail inline** | ⚠️ DISCONNECTED | Guardrail engine exists but Brain doesn't call it automatically |
| **Autonomy persistence** | ⚠️ IN-MEMORY | Plans lost on container restart |

---

## 🧹 PHASE 2 & 3 — CLEANUP PLAN

### Files to DELETE (safe, will not break system)

#### Root Level (14 files)
```
DELETE:
├── as on 22032026.txt          # 🚨 PLAINTEXT SECRETS — delete + rotate tokens
├── contacts.csv                # 🚨 PII DATA — personal contacts dump
├── AUDIT_REPORT.md             # Superseded (Mar 7)
├── AUDIT_REPORT_2026-03-10.md  # Superseded
├── INFRASTRUCTURE_AUDIT_REPORT.md  # Duplicate of above
├── SYSTEM_AUDIT_REPORT.md      # Covered by this report
├── GITOPS_AUDIT_REPORT_2026-03-18.md  # Single snapshot
├── PHASE11_AUDIT_REPORT.md     # Old phase report
├── PHASE11_REMEDIATION_REPORT.md
├── PHASE4_5_DEPLOYMENT_REPORT.md
├── PHASE5_DEPLOYMENT_REPORT.md
├── AI_WATCHDOG_DEPLOYMENT_REPORT.md
├── DASHBOARD_DEPLOYMENT_REPORT.md
├── DEPLOYMENT_MANIFEST.md      # Redundant with PRE_DEPLOY_CHECKLIST
├── PRE_DEPLOY_CHECKLIST.md     # Redundant with above
├── LOCAL_REMEDIATION_REPORT.md
├── VERIFICATION_REPORT.md
├── gen-secrets.sh              # Stub → scripts/gen-secrets.sh
├── test_login.py               # Duplicate of test_login2.py
├── docker-compose.yaml         # LEGACY monolithic
├── dograh-docker-compose.yaml  # LEGACY standalone
├── dograh.env.template         # For legacy standalone only
```

#### Fazle-AI stack
```
DELETE:
├── fazle-ai/fazle-docker-compose.yaml  # LEGACY pre-Phase-5
```

#### Deployment Package
```
DELETE:
├── deployment-package/MANIFEST.txt     # Redundant subset of DEPLOYMENT_MANIFEST.md
├── deployment-package/.env.secure      # Contains real passwords — get off repo
├── deployment-package/fix-secrets.sh   # One-time fix already applied
```

#### Scripts (16 files)
```
DELETE from scripts/:
├── ollama-keepalive.sh
├── deploy-api-blue.sh
├── test-auth.sh
├── test-multimodal.sh
├── check-projects.sh
├── verify-dashboard.sh
├── bench_warm.py
├── bench_clean.py
├── test-brain-health.py
├── test-api-dns.py
├── test-api-dns.js
├── test_brain_perf.py
├── check-livekit-api.py
├── fix_interval.py
├── fix_learning.py
├── fix_learning2.py
```

#### Empty/Stale Directories
```
DELETE:
├── monitoring/grafana/provisioning/alerting/    # Empty
├── monitoring/grafana/provisioning/dashboards/  # Empty
```

### Files to MERGE

| Source Files | Target | Action |
|-------------|--------|--------|
| `production_readme.md` | `README.md` | Merge ops section into README, delete `production_readme.md` |
| `monitoring/dashboards/*.json` + `monitoring/grafana/dashboards/*.json` + `observability/grafana/dashboards/*.json` | `configs/grafana/dashboards/` | Move all unique dashboards, deduplicate `ai-infrastructure-dashboard.json`, delete `monitoring/` and `observability/` dirs |
| `scripts/rollback.sh` + `scripts/rollback-vps.sh` | `scripts/rollback.sh` | Merge VPS rollback logic into main rollback |
| `scripts/debug.sh` + `scripts/diagnose.sh` | `scripts/diagnose.sh` | Merge debug into diagnose |
| `local-validation/checklist.md` | Keep as-is or merge into `migration-checklist.md` | Low priority |
| `test_login2.py` → rename to `test_login.py` | Root level | Rename |

### Files to ARCHIVE (move to `scripts/archive/`)

```
ARCHIVE from scripts/:
├── deploy.sh
├── deploy-phase6.sh
├── rollback-phase6.sh
├── phase0-snapshot.sh
├── phase1-disk-cleanup.sh
├── phase3-prep.sh
├── phase3-migrate.sh
├── phase3-migrate-fazle.sh
├── phase3-fix-volumes.sh
├── phase6-verify.sh
├── sudo-fix.sh
├── activate-vision.sh
├── final-verify.sh
├── patch_phase5_settings.py
├── test-openai-final.py

ARCHIVE from root:
├── migration-deploy.sh
├── verify-remediation.sh
```

### Files to KEEP (no changes)

```
KEEP:
├── README.md                    # After merging production_readme.md
├── UPGRADE_ROADMAP.md
├── zero-downtime-deploy.md
├── migration-checklist.md
├── Features_new_deploy.txt
├── pytest.ini
├── .gitignore                   # Update with contacts.csv, *.csv
├── .pre-commit-config.yaml
├── ai-infra/docker-compose.yaml
├── dograh/docker-compose.yaml   # Dograh without LiveKit
├── fazle-ai/docker-compose.yaml # Full Fazle stack
├── configs/                     # All config files
├── db/                          # SQL scripts
├── docs/                        # 8 operational runbooks
├── fazle-system/                # All microservice code
├── frontend/                    # Next.js dashboard
├── personality/                 # AI persona files
├── tests/                       # Unit tests
├── scripts/ (30+ operational)   # After cleanup
├── ai-watchdog/                 # Self-healing
├── ai-control-plane/            # AI DevOps
├── local-validation/            # Pre-deploy checks
├── ops/                         # Systemd + LetsEncrypt
```

---

## 🔑 PHASE 4 — REQUIRED CREDENTIALS REPORT

### 🚨 IMMEDIATE — System will crash without these

| Credential | Where to set | How to get | Mandatory |
|-----------|-------------|-----------|-----------|
| `FAZLE_JWT_SECRET` | VPS `.env` | `openssl rand -base64 48 \| tr -dc 'a-zA-Z0-9' \| head -c 48` | **YES — API crashes without it** |
| `OPENAI_API_KEY` | VPS `.env` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | YES for GPT-4o (Ollama fallback works without it) |

### Meta / WhatsApp (for social features)

| Credential | Where to set | How to get | Mandatory |
|-----------|-------------|-----------|-----------|
| `SOCIAL_WHATSAPP_API_TOKEN` | VPS `.env` | Meta Business Suite → WhatsApp → API Setup → Generate permanent token | YES for WhatsApp |
| `SOCIAL_WHATSAPP_PHONE_NUMBER_ID` | VPS `.env` | Meta Business Suite → WhatsApp → Phone Numbers → Copy ID | YES for WhatsApp |
| `SOCIAL_WHATSAPP_API_URL` | VPS `.env` | Default: `https://graph.facebook.com/v19.0` | Optional (has default) |

### Facebook (for social features)

| Credential | Where to set | How to get | Mandatory |
|-----------|-------------|-----------|-----------|
| `SOCIAL_FACEBOOK_PAGE_ACCESS_TOKEN` | VPS `.env` | Meta Business Suite → Page Settings → Advanced → Page Access Token (never-expiring) | YES for Facebook |
| `SOCIAL_FACEBOOK_PAGE_ID` | VPS `.env` | Facebook Page → About → Page ID | YES for Facebook |

### Security

| Credential | Where to set | How to get | Mandatory |
|-----------|-------------|-----------|-----------|
| `SOCIAL_ENCRYPTION_KEY` | VPS `.env` | `openssl rand -base64 32` | YES (prevents plaintext credential storage) |
| `SOCIAL_VERIFY_TOKEN` | VPS `.env` | Any random string, must match Meta webhook config | YES (change from default) |

### Search

| Credential | Where to set | How to get | Mandatory |
|-----------|-------------|-----------|-----------|
| `SERPER_API_KEY` | VPS `.env` | [serper.dev](https://serper.dev) — free 2500 queries | Optional (web search feature) |
| `TAVILY_API_KEY` | VPS `.env` | [tavily.com](https://tavily.com) — free tier | Optional (fallback search) |

### Voice (optional enhancements)

| Credential | Where to set | How to get | Mandatory |
|-----------|-------------|-----------|-----------|
| `ELEVENLABS_API_KEY` | Not implemented | N/A | ❌ Not implemented in code |
| `ELEVENLABS_VOICE_ID` | Not implemented | N/A | ❌ Not implemented in code |

### Summary: What YOU must provide

```bash
# MANDATORY (generate these now)
FAZLE_JWT_SECRET=<generate: openssl rand -base64 48>
SOCIAL_ENCRYPTION_KEY=<generate: openssl rand -base64 32>
SOCIAL_VERIFY_TOKEN=<generate: openssl rand -hex 16>

# MANDATORY (get from providers)
OPENAI_API_KEY=sk-...

# FOR SOCIAL FEATURES (get from Meta Business Suite)
SOCIAL_WHATSAPP_API_TOKEN=EAA...
SOCIAL_WHATSAPP_PHONE_NUMBER_ID=100...
SOCIAL_FACEBOOK_PAGE_ACCESS_TOKEN=EAA...
SOCIAL_FACEBOOK_PAGE_ID=...

# OPTIONAL (for web search)
SERPER_API_KEY=...
```

---

## 🧪 PHASE 5 — TESTING GUIDE

### Test 1: Webhook Verification (WhatsApp)

After setting credentials and deploying:

```bash
# From any machine — this simulates Meta's verification handshake
curl -s "https://iamazim.com/api/fazle/social/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=YOUR_VERIFY_TOKEN&hub.challenge=test123"

# Expected: plain text "test123" (HTTP 200)
# If you get 403: verify token mismatch
# If you get 404: social engine not running or route not proxied
```

### Test 2: WhatsApp Send Message

```bash
curl -s -X POST https://iamazim.com/api/fazle/social/whatsapp/send \
  -H "X-API-Key: YOUR_FAZLE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"to": "YOUR_PHONE_WITH_COUNTRY_CODE", "message": "Hello from Fazle AI!"}'

# Expected: {"status": "sent", "message_id": "wamid.xxx"}
# If error: check SOCIAL_WHATSAPP_API_TOKEN and PHONE_NUMBER_ID
```

### Test 3: Facebook Comment Reply

```bash
curl -s -X POST https://iamazim.com/api/fazle/social/facebook/comment \
  -H "X-API-Key: YOUR_FAZLE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"target_id": "POST_OR_COMMENT_ID", "message": "Thanks for your comment!"}'

# Expected: {"status": "replied", "comment_id": "xxx"}
# If error: check SOCIAL_FACEBOOK_PAGE_ACCESS_TOKEN
```

### Test 4: Brain Health (basic)

```bash
# Direct brain endpoint
curl -s http://localhost:8200/health

# Expected: {"status": "ok", ...}

# Chat test via API
curl -s -X POST https://iamazim.com/api/fazle/chat \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, who are you?"}'

# Expected: {"reply": "...", ...} — AI response based on persona
```

### Test 5: Social Engine Health

```bash
curl -s http://localhost:9800/health

# Expected: {"status": "ok", "platform_status": {...}}
```

---

## 🛠 PHASE 6 — REFACTOR PLAN (Minimal Changes)

### Fix 1: Add HMAC Webhook Signature Validation

**Modify existing file:** `fazle-system/social-engine/main.py`

Add `X-Hub-Signature-256` validation to both `/whatsapp/webhook` POST and `/facebook/webhook` POST handlers. This is a ~20-line change using `hmac.compare_digest()` with the Meta App Secret.

### Fix 2: Add Missing `FAZLE_JWT_SECRET` to VPS .env

**Action:** SSH to VPS, generate and append:
```bash
FAZLE_JWT_SECRET=$(openssl rand -base64 48 | tr -dc 'a-zA-Z0-9' | head -c 48)
echo "FAZLE_JWT_SECRET=$FAZLE_JWT_SECRET" >> ~/ai-call-platform/.env
```

### Fix 3: Restrict Workflow Engine CORS

**Modify existing file:** `fazle-system/workflow-engine/main.py`

Change `allow_origins=["*"]` to `allow_origins=["https://iamazim.com", "https://fazle.iamazim.com"]`.

### Fix 4: Restrict Guardrail Engine CORS

**Modify existing file:** `fazle-system/guardrail-engine/main.py`

Same CORS fix as workflow engine.

### Fix 5: Update .gitignore

**Modify existing file:** `.gitignore`

Add: `contacts.csv`, `*.csv`, `as on*`, `deployment-package/*.secure`

### Fix 6: Resolve LiveKit/Coturn Port Conflict

**Decision:** Keep LiveKit/Coturn in `ai-infra/docker-compose.yaml` only. Use `dograh/docker-compose.yaml` (without LiveKit) for the Dograh stack. Rename `dograh/dograh-docker-compose.yaml` → archive.

---

## 🚀 PHASE 7 — EXECUTION PLAN

### What Copilot Will Handle (automated):

1. ✅ Generate this audit report
2. ✅ Identify all duplicates and decisions
3. Can apply: CORS fixes, HMAC validation, .gitignore update
4. Can apply: File deletions (with your approval)

### What YOU Must Do (manual):

1. **🚨 IMMEDIATE:** Delete `as on 22032026.txt` from git history (contains real tokens)
   ```bash
   git filter-branch --force --index-filter 'git rm --cached --ignore-unmatch "as on 22032026.txt"' HEAD
   git push --force
   ```
2. **🚨 IMMEDIATE:** Rotate ALL Meta/WhatsApp tokens exposed in that file
3. **Provide credentials:** OPENAI_API_KEY, Meta tokens (see Phase 4)
4. **SSH to VPS:** Add `FAZLE_JWT_SECRET` and social credentials to `.env`
5. **Approve cleanup:** Review the delete/merge lists, then I can execute

### Post-Cleanup File Count

| Category | Before | After |
|----------|--------|-------|
| Root markdown files | 22 | **5** |
| Root scripts/tests | 6 | **2** |
| Docker compose files | 7 | **3** |
| scripts/ directory | 80+ | **~35** |
| Dashboard directories | 3 | **1** |
| Total files at root | 30+ | **~12** |

---

## ✅ FINAL VERDICT

The system architecture is **sound** — the three-stack Docker deployment, Fazle microservices, AI Brain, and social engine code are well-built. But the repo is **severely bloated** with historical artifacts:

- **17 stale reports** that document past work but add no operational value
- **4 legacy compose files** that conflict with the current three-stack architecture
- **30+ redundant scripts** from migration phases already completed
- **2 files with production secrets** committed to version control

After executing this cleanup plan:
- Root directory: 30+ files → ~12 files
- Scripts: 80+ → ~35 essential operational scripts
- Compose files: 7 → 3 (one per stack)
- Dashboard dirs: 3 → 1 consolidated location
- Zero secrets in repo

**The system becomes SIMPLER, not more complex.**
