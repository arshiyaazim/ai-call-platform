#!/usr/bin/env bash
# ============================================================
# deploy-phase6.sh — Migrate from monolithic to three-stack
# Safe if interrupted: re-run from any step via --step N
# ============================================================
# Usage:
#   ./scripts/deploy-phase6.sh           # full run
#   ./scripts/deploy-phase6.sh --step 4  # resume from step 4
#   ./scripts/deploy-phase6.sh --dry-run # show plan only
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$HOME/backups"
BACKUP_FILE="$BACKUP_DIR/pre-phase6-$TIMESTAMP.tar.gz"
LOG_FILE="$ROOT_DIR/phase6-deploy-$TIMESTAMP.log"
ENV_FILE="$ROOT_DIR/.env"
MONO_COMPOSE="$ROOT_DIR/docker-compose.yaml"
START_STEP=1
DRY_RUN=false

# ── Parse args ───────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --step) START_STEP="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

# ── Logging ──────────────────────────────────────────────────
exec > >(tee -a "$LOG_FILE") 2>&1

log() { echo "[$(date '+%H:%M:%S')] $*"; }
die() { log "FATAL: $*"; exit 1; }
step_banner() { echo ""; log "════════════════════════════════════════"; log "STEP $1: $2"; log "════════════════════════════════════════"; }

# ── Dry-run mode ─────────────────────────────────────────────
if $DRY_RUN; then
  echo "Phase 6 Migration Plan (dry-run)"
  echo "================================"
  echo "Step 1: Pre-flight checks (disk, env, compose files)"
  echo "Step 2: Backup current docker-compose.yaml + .env + configs"
  echo "Step 3: Stop fazle-api-blue (orphan from blue/green deploy)"
  echo "Step 4: docker compose down (monolithic) — stops all, removes containers"
  echo "Step 5: Clean up leftover networks/containers"
  echo "Step 6: Create external networks"
  echo "Step 7: Start ai-infra stack (databases, caches, monitoring)"
  echo "Step 8: Wait for infrastructure healthy"
  echo "Step 9: Start dograh stack"
  echo "Step 10: Wait for dograh healthy"
  echo "Step 11: Start fazle-ai stack (with rebuild)"
  echo "Step 12: Post-deploy verification"
  echo ""
  echo "Rollback: ./scripts/rollback-phase6.sh"
  exit 0
fi

# ════════════════════════════════════════════════════════════
# STEP 1: Pre-flight checks
# ════════════════════════════════════════════════════════════
if [ "$START_STEP" -le 1 ]; then
  step_banner 1 "Pre-flight checks"

  # Check .env
  [ -f "$ENV_FILE" ] || die ".env not found at $ENV_FILE"
  log "[OK] .env exists"

  # Check compose files
  for f in ai-infra/docker-compose.yaml dograh/docker-compose.yaml fazle-ai/docker-compose.yaml; do
    [ -f "$ROOT_DIR/$f" ] || die "Missing: $f"
    log "[OK] $f exists"
  done

  # Check monolithic compose exists (for backup)
  [ -f "$MONO_COMPOSE" ] || die "Monolithic docker-compose.yaml not found"
  log "[OK] Monolithic docker-compose.yaml exists"

  # Check scripts
  for s in create-networks.sh stack-up.sh stack-down.sh stack-status.sh; do
    [ -f "$SCRIPT_DIR/$s" ] || die "Missing script: $s"
  done
  log "[OK] All stack management scripts present"

  # Check disk space (need at least 2GB free)
  AVAIL_KB=$(df --output=avail "$ROOT_DIR" | tail -1 | tr -d ' ')
  AVAIL_MB=$((AVAIL_KB / 1024))
  if [ "$AVAIL_MB" -lt 2048 ]; then
    die "Insufficient disk space: ${AVAIL_MB}MB available (need 2048MB)"
  fi
  log "[OK] Disk space: ${AVAIL_MB}MB available"

  # Check docker + compose
  docker --version >/dev/null 2>&1 || die "Docker not found"
  docker compose version >/dev/null 2>&1 || die "Docker Compose not found"
  log "[OK] Docker $(docker --version | grep -oP 'version \K[^,]+')"

  log "Pre-flight checks passed"
fi

# ════════════════════════════════════════════════════════════
# STEP 2: Backup
# ════════════════════════════════════════════════════════════
if [ "$START_STEP" -le 2 ]; then
  step_banner 2 "Create backup"

  mkdir -p "$BACKUP_DIR"
  tar czf "$BACKUP_FILE" \
    -C "$ROOT_DIR" \
    docker-compose.yaml \
    .env \
    configs/ \
    scripts/ \
    2>/dev/null || true

  BACKUP_SIZE=$(du -sh "$BACKUP_FILE" | cut -f1)
  log "[OK] Backup created: $BACKUP_FILE ($BACKUP_SIZE)"
  log "     Rollback: ./scripts/rollback-phase6.sh $BACKUP_FILE"
fi

# ════════════════════════════════════════════════════════════
# STEP 3: Stop orphan blue/green container
# ════════════════════════════════════════════════════════════
if [ "$START_STEP" -le 3 ]; then
  step_banner 3 "Stop orphan fazle-api-blue container"

  if docker ps -a --format '{{.Names}}' | grep -q '^fazle-api-blue$'; then
    log "Stopping fazle-api-blue..."
    docker stop fazle-api-blue 2>/dev/null || true
    docker rm fazle-api-blue 2>/dev/null || true
    log "[OK] fazle-api-blue removed"
  else
    log "[SKIP] fazle-api-blue not found (already cleaned)"
  fi
fi

# ════════════════════════════════════════════════════════════
# STEP 4: Stop monolithic stack
# ════════════════════════════════════════════════════════════
if [ "$START_STEP" -le 4 ]; then
  step_banner 4 "Stop monolithic docker-compose"

  if [ -f "$MONO_COMPOSE" ]; then
    log "Running docker compose down..."
    docker compose -f "$MONO_COMPOSE" --env-file "$ENV_FILE" -p ai-call-platform down --timeout 30 || {
      log "[WARN] docker compose down failed — trying to stop individual containers"
      docker compose -f "$MONO_COMPOSE" --env-file "$ENV_FILE" -p ai-call-platform stop --timeout 30 || true
      docker compose -f "$MONO_COMPOSE" --env-file "$ENV_FILE" -p ai-call-platform rm -f || true
    }
    log "[OK] Monolithic stack stopped"
  else
    log "[SKIP] No monolithic compose file found"
  fi

  # Record after-state
  REMAINING=$(docker ps --format '{{.Names}}' | wc -l)
  log "Containers still running: $REMAINING"
  if [ "$REMAINING" -gt 0 ]; then
    log "[WARN] Remaining containers:"
    docker ps --format '  {{.Names}} ({{.Image}})' | head -10
  fi
fi

# ════════════════════════════════════════════════════════════
# STEP 5: Clean up leftovers
# ════════════════════════════════════════════════════════════
if [ "$START_STEP" -le 5 ]; then
  step_banner 5 "Clean up leftover resources"

  # Remove leftover compose-prefixed network
  docker network rm ai-call-platform_app-network 2>/dev/null && \
    log "[OK] Removed leftover network ai-call-platform_app-network" || \
    log "[SKIP] ai-call-platform_app-network not found"

  # Remove any other ai-call-platform_ prefixed networks (compose leftovers)
  for net in $(docker network ls --format '{{.Name}}' | grep '^ai-call-platform_' || true); do
    docker network rm "$net" 2>/dev/null && \
      log "[OK] Removed leftover network $net" || \
      log "[SKIP] Could not remove $net (may be in use)"
  done

  # Clean unused images to free space (optional, non-fatal)
  # docker image prune -f >/dev/null 2>&1 && log "[OK] Pruned dangling images" || true

  log "Cleanup complete"
fi

# ════════════════════════════════════════════════════════════
# STEP 6: Create external networks
# ════════════════════════════════════════════════════════════
if [ "$START_STEP" -le 6 ]; then
  step_banner 6 "Create external Docker networks"

  chmod +x "$SCRIPT_DIR/create-networks.sh"
  "$SCRIPT_DIR/create-networks.sh"
  log "[OK] All networks ready"
fi

# ════════════════════════════════════════════════════════════
# STEP 7: Start ai-infra stack
# ════════════════════════════════════════════════════════════
if [ "$START_STEP" -le 7 ]; then
  step_banner 7 "Start ai-infra stack (databases, caches, monitoring)"

  docker compose \
    -f "$ROOT_DIR/ai-infra/docker-compose.yaml" \
    --env-file "$ENV_FILE" \
    -p ai-infra \
    up -d

  log "[OK] ai-infra stack started"
fi

# ════════════════════════════════════════════════════════════
# STEP 8: Wait for infrastructure healthy
# ════════════════════════════════════════════════════════════
if [ "$START_STEP" -le 8 ]; then
  step_banner 8 "Wait for infrastructure services to be healthy"

  wait_for() {
    local name="$1"
    local timeout="${2:-120}"
    local elapsed=0
    while [ $elapsed -lt "$timeout" ]; do
      local status
      status=$(docker inspect --format='{{.State.Health.Status}}' "$name" 2>/dev/null || echo "missing")
      case "$status" in
        healthy) log "  [OK] $name is healthy"; return 0 ;;
        missing) log "  [WAIT] $name container not found yet..."; ;;
      esac
      sleep 5
      elapsed=$((elapsed + 5))
    done
    log "  [WARN] $name not healthy after ${timeout}s — continuing anyway"
    return 0
  }

  wait_for "ai-postgres" 90
  wait_for "ai-redis" 60
  wait_for "ollama" 120
  wait_for "prometheus" 60
  wait_for "grafana" 60

  log "Infrastructure health checks complete"
fi

# ════════════════════════════════════════════════════════════
# STEP 9: Start dograh stack
# ════════════════════════════════════════════════════════════
if [ "$START_STEP" -le 9 ]; then
  step_banner 9 "Start dograh stack"

  docker compose \
    -f "$ROOT_DIR/dograh/docker-compose.yaml" \
    --env-file "$ENV_FILE" \
    -p dograh \
    up -d

  log "[OK] dograh stack started"
fi

# ════════════════════════════════════════════════════════════
# STEP 10: Wait for dograh healthy
# ════════════════════════════════════════════════════════════
if [ "$START_STEP" -le 10 ]; then
  step_banner 10 "Wait for dograh services to be healthy"

  wait_for() {
    local name="$1"
    local timeout="${2:-120}"
    local elapsed=0
    while [ $elapsed -lt "$timeout" ]; do
      local status
      status=$(docker inspect --format='{{.State.Health.Status}}' "$name" 2>/dev/null || echo "missing")
      case "$status" in
        healthy) log "  [OK] $name is healthy"; return 0 ;;
      esac
      sleep 5
      elapsed=$((elapsed + 5))
    done
    log "  [WARN] $name not healthy after ${timeout}s — continuing anyway"
    return 0
  }

  wait_for "dograh-api" 120
  wait_for "dograh-ui" 60

  log "Dograh health checks complete"
fi

# ════════════════════════════════════════════════════════════
# STEP 11: Start fazle-ai stack (with rebuild)
# ════════════════════════════════════════════════════════════
if [ "$START_STEP" -le 11 ]; then
  step_banner 11 "Start fazle-ai stack (rebuild from updated source)"

  docker compose \
    -f "$ROOT_DIR/fazle-ai/docker-compose.yaml" \
    --env-file "$ENV_FILE" \
    -p fazle-ai \
    up -d --build

  log "[OK] fazle-ai stack started (images rebuilt)"
fi

# ════════════════════════════════════════════════════════════
# STEP 12: Post-deploy verification
# ════════════════════════════════════════════════════════════
if [ "$START_STEP" -le 12 ]; then
  step_banner 12 "Post-deploy verification"

  log "── Container status ──"
  docker ps --format "table {{.Names}}\t{{.Status}}" | sort

  log ""
  log "── Health summary ──"
  TOTAL=$(docker ps --format '{{.Names}}' | wc -l)
  HEALTHY=$(docker ps --filter 'health=healthy' --format '{{.Names}}' | wc -l)
  UNHEALTHY=$(docker ps --filter 'health=unhealthy' --format '{{.Names}}' | wc -l)
  STARTING=$(docker ps --filter 'health=starting' --format '{{.Names}}' | wc -l)

  log "Total containers: $TOTAL"
  log "Healthy: $HEALTHY"
  log "Starting: $STARTING"
  log "Unhealthy: $UNHEALTHY"

  if [ "$UNHEALTHY" -gt 0 ]; then
    log "[WARN] Unhealthy containers:"
    docker ps --filter 'health=unhealthy' --format '  {{.Names}} — {{.Status}}'
  fi

  log ""
  log "── Volume check ──"
  docker volume ls --format '{{.Name}}' | grep 'ai-call-platform_' | sort | while read -r vol; do
    log "  [OK] Volume: $vol"
  done

  log ""
  log "── Network check ──"
  for net in app-network db-network ai-network monitoring-network; do
    if docker network inspect "$net" >/dev/null 2>&1; then
      CONNECTED=$(docker network inspect "$net" --format '{{range .Containers}}{{.Name}} {{end}}' | wc -w)
      log "  [OK] $net ($CONNECTED containers connected)"
    else
      log "  [FAIL] $net does not exist!"
    fi
  done

  log ""
  log "── Restart policy check ──"
  BAD_RESTART=$(docker ps --format '{{.Names}}' | while read -r c; do
    POLICY=$(docker inspect --format='{{.HostConfig.RestartPolicy.Name}}' "$c" 2>/dev/null || echo "unknown")
    if [ "$POLICY" != "unless-stopped" ] && [ "$POLICY" != "always" ]; then
      echo "$c ($POLICY)"
    fi
  done)
  if [ -z "$BAD_RESTART" ]; then
    log "  [OK] All containers have restart policy set"
  else
    log "  [WARN] Containers without proper restart policy:"
    echo "$BAD_RESTART" | while read -r line; do log "    $line"; done
  fi

  log ""
  log "── Quick endpoint checks ──"
  for svc in "dograh-api:8000/health" "fazle-api:8100/health" "fazle-brain:8200/health" "fazle-memory:8300/health"; do
    NAME="${svc%%:*}"
    ENDPOINT="${svc#*:}"
    IP=$(docker inspect --format='{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$NAME" 2>/dev/null | head -1)
    if [ -n "$IP" ]; then
      HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://$IP:$ENDPOINT" 2>/dev/null || echo "000")
      if [ "$HTTP_CODE" = "200" ]; then
        log "  [OK] $NAME /health → $HTTP_CODE"
      else
        log "  [WARN] $NAME /health → $HTTP_CODE"
      fi
    else
      log "  [SKIP] $NAME — no IP found"
    fi
  done

  log ""
  log "── Disk usage ──"
  df -h / | tail -1 | awk '{print "  Used: "$3" / "$2" ("$5" used), Available: "$4}'

  echo ""
  echo "═══════════════════════════════════════════════════════"
  log "Phase 6 migration complete!"
  log "Log file: $LOG_FILE"
  log "Backup: $BACKUP_FILE"
  log ""
  log "If anything is wrong, rollback with:"
  log "  ./scripts/rollback-phase6.sh $BACKUP_FILE"
  echo "═══════════════════════════════════════════════════════"
fi
