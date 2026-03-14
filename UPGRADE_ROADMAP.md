# Upgrade Roadmap — vps-deploy

## Short Term (Immediate)

### Config & Routing (All Complete)
- [x] Nginx `/api/config/*` routed to frontend before `/api/` catch-all
- [x] LiveKit & Coturn env var expansion via entrypoint scripts (`sed`)
- [x] Coturn deprecated `no-tlsv1` / `no-tlsv1_1` directives removed
- [x] Coturn TLS certs mounted as individual files, container runs as root
- [x] UI health check uses `127.0.0.1` (not `localhost`) to avoid IPv6 issues
- [x] NEXT_PUBLIC_* not needed — OSS mode suppresses Stack Auth via `/api/config/auth`

### Dependencies & Environment
- [x] `PyPDF2>=3.0.0` and `python-docx>=1.1.0` added to `fazle-system/api/requirements.txt`
- [ ] Verify deployed configs match repo: run `bash scripts/verify-configs.sh` on VPS
- [ ] Review all service images for available updates (`docker compose pull` dry-run)

---

## Medium Term (Next 2–4 Weeks)

### Scheduler Refactoring (Complete)
- [x] `AsyncIOScheduler` now uses `asyncio.to_thread()` for sync DB calls
- [x] Added `misfire_grace_time=300` and `coalesce=True` to prevent silent skips
- [ ] Consider migrating to APScheduler 4.x for native async job stores when stable

### Security Hardening (Complete)
- [x] SSRF protection enhanced: `getaddrinfo()` resolves both IPv4 and IPv6
- [x] PII redaction (`redact_pii()`) added to trainer pipeline before memory storage
- [ ] Add rate limiting to Fazle API endpoints (currently no rate limiting on internal services)
- [ ] Review CORS `allow_origins` on all Fazle services — tighten to exact domains only

### Grafana Alert Rules
Add these alerting rules in Grafana (or via provisioned alert config):

| Alert | PromQL / Condition | Threshold |
|-------|-------------------|-----------|
| API High Error Rate | `rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])` | > 5% for 5min |
| Service Down | `up{job=~"dograh-api|fazle-.*"} == 0` | for 2min |
| High Memory Usage | `container_memory_usage_bytes / container_spec_memory_limit_bytes` | > 85% for 10min |
| Disk Space Low | `node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}` | < 15% |
| PostgreSQL Connections | `pg_stat_activity_count` | > 80% of max |
| Redis Memory | `redis_memory_used_bytes / redis_memory_max_bytes` | > 90% |
| LiveKit Room Stuck | `livekit_room_duration_seconds` | > 7200s (2hr) |
| Certificate Expiry | `probe_ssl_earliest_cert_expiry - time()` | < 7 days |
| Container Restart Loop | `increase(container_restart_count[1h])` | > 3 |

---

## Long Term (Ongoing)

### Dependency Auditing
- [ ] Set up automated dependency scanning (e.g., Dependabot, Renovate, or `pip-audit` in CI)
- [ ] Pin all Python dependencies to exact versions (already done for most)
- [ ] Schedule quarterly review of base Docker images for security patches
- [ ] Track Coturn, LiveKit, and Grafana release notes for breaking changes

### Config Validation & CI/CD
- [ ] Add a CI step that runs `docker compose config` to validate compose syntax
- [ ] Add a CI step that lints Nginx configs: `nginx -t` in a container
- [ ] Add a CI step that runs `scripts/verify-configs.sh` against a test environment
- [ ] Automate deployment with a pipeline: lint → build → test → deploy → smoke-test
- [ ] Store secrets in a vault (HashiCorp Vault, Doppler, or GitHub Actions secrets) instead of `.env` files

### Container Hardening
- [ ] Add `read_only: true` to all remaining containers (postgres, redis, minio, livekit, coturn)
- [ ] Drop all capabilities and add only required ones (`cap_drop: [ALL]`, `cap_add: [...]`)
- [ ] Set `no-new-privileges: true` on all containers (already on cadvisor)
- [ ] Use non-root users where possible (Coturn currently requires root for TLS certs)
- [ ] Scan container images for vulnerabilities: `trivy image <image>` in CI

### Monitoring Improvements
- [ ] Add structured JSON logging to all Fazle services (partially done for LiveKit)
- [ ] Set up Loki log-based alerts for error patterns (e.g., "LLM extraction failed")
- [ ] Add distributed tracing (OpenTelemetry) across Fazle service boundaries
- [ ] Create Grafana dashboards per service with latency percentiles (p50, p95, p99)
