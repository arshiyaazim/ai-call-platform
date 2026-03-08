# PRE-DEPLOYMENT CHECKLIST

**Branch:** `hotfix/audit-remediation-local`  
**Target:** VPS `5.189.131.48` (`azim@`)  
**Deploy Dir:** `/home/azim/ai-call-platform`  

---

## Security Issues Resolved

- [x] **P0: Auth bypass** — Empty `FAZLE_API_KEY` no longer silently skips auth (returns 500)
- [x] **P0: Privileged container** — cadvisor `privileged: true` replaced with `cap_add`
- [x] **P0: CORS wildcard** — All 6 Fazle services restrict origins to known domains
- [x] **P0: MinIO CORS** — Restricted from `*` to `iamazim.com, fazle.iamazim.com`
- [x] **P1: Volatile data** — Task engine uses PostgreSQL, Brain uses Redis
- [x] **P1: Image pinning** — 13 images pinned to specific versions
- [x] **P1: Coturn TLS** — Cert paths fixed to `/etc/coturn/certs/`
- [x] **P1: Input validation** — Pydantic schemas with max lengths, regex patterns, type validation
- [x] **P2: Next.js upgrade** — 14.2.21 → 14.2.35 (patches 6 CVEs)
- [x] **P2: Healthchecks** — Added to coturn and cloudflared

## Database Migrations Required

- [x] Migration script prepared: `scripts/db-migrate.sh`
- [x] SQL file: `fazle-system/tasks/migrations/001_scheduler_tables.sql`
- [ ] **ACTION:** Run `bash scripts/db-migrate.sh` on VPS after code deploy

## Rollback Strategy

- **Current VPS commit:** Record via `ssh azim@5.189.131.48 "cd ~/ai-call-platform && git rev-parse HEAD"`
- **Rollback script:** `scripts/rollback-vps.sh`
- **Manual rollback:** Restore `backups/docker-compose-*.yaml` and `backups/env-*.bak`
- **DB rollback:** `docker exec ai-postgres psql -U postgres -c "DROP TABLE IF EXISTS fazle_tasks;"`

## Secrets Transfer

- [ ] **ACTION:** Generate fresh secrets on VPS (or securely transfer `.env.secure`)
- [ ] Transfer method: `scp deployment-package/.env.secure azim@5.189.131.48:/tmp/`
- [ ] On VPS: merge new env vars into existing `.env` (do NOT overwrite — keep existing DB passwords)
- [ ] New required env vars:
  - `FAZLE_API_KEY` (64-char, must not be empty)
  - `DATABASE_URL` (PostgreSQL connection string for task engine)
  - `GRAFANA_ADMIN_PASSWORD`

## Pre-Deploy VPS Actions

- [ ] Run backup: `bash scripts/backup.sh`
- [ ] Record current commit hash to `ROLLBACK_TARGET.txt`
- [ ] Verify disk space: `df -h /` (need ~500MB free)
- [ ] Verify Docker running: `docker info >/dev/null 2>&1`

## Post-Deploy Actions

- [ ] Run `bash scripts/db-migrate.sh`
- [ ] Run `bash scripts/setup-ollama.sh` (if models not already pulled)
- [ ] Run `bash scripts/health-check.sh`
- [ ] Verify all 23 containers healthy
- [ ] Test endpoints:
  - `curl -s https://api.iamazim.com/api/v1/health`
  - `curl -s http://localhost:8100/health` (Fazle API)
  - `curl -s http://localhost:3020` (Fazle UI)

## Sign-Off

- [ ] All local validation gates passed (Phases 0–6)
- [ ] Deployment package created and verified
- [ ] Rollback plan tested (script syntax validated)
- [ ] Ready to deploy: **YES / NO**
