#!/usr/bin/env bash
# ============================================================
# rollback-phase6.sh — Revert three-stack back to monolithic
# Restores the original docker-compose.yaml and starts it.
# Target: < 60 seconds
# ============================================================
# Usage:
#   ./scripts/rollback-phase6.sh                     # auto-find latest backup
#   ./scripts/rollback-phase6.sh /path/to/backup.tar.gz  # specific backup
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$ROOT_DIR/.env"
BACKUP_DIR="$HOME/backups"

log() { echo "[$(date '+%H:%M:%S')] $*"; }
die() { log "FATAL: $*"; exit 1; }

# ── Resolve backup file ─────────────────────────────────────
if [ "${1:-}" != "" ] && [ -f "$1" ]; then
  BACKUP_FILE="$1"
else
  # Auto-find the latest backup
  BACKUP_FILE=$(ls -t "$BACKUP_DIR"/pre-phase6-*.tar.gz 2>/dev/null | head -1 || true)
  [ -n "$BACKUP_FILE" ] && [ -f "$BACKUP_FILE" ] || die "No backup found. Provide path: $0 /path/to/backup.tar.gz"
fi

log "Using backup: $BACKUP_FILE"

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  ROLLBACK: Three-stack → Monolithic"
echo "  Backup: $BACKUP_FILE"
echo "═══════════════════════════════════════════════════════"
echo ""
read -p "Are you sure you want to rollback? [y/N] " -r REPLY
echo ""
if [[ ! "$REPLY" =~ ^[Yy]$ ]]; then
  log "Rollback cancelled."
  exit 0
fi

START_TIME=$(date +%s)

# ── Step 1: Stop three-stack ─────────────────────────────────
log "Stopping three-stack services..."

for stack in fazle-ai dograh ai-infra; do
  COMPOSE="$ROOT_DIR/$stack/docker-compose.yaml"
  if [ -f "$COMPOSE" ]; then
    log "  Stopping $stack..."
    docker compose -f "$COMPOSE" --env-file "$ENV_FILE" -p "$stack" down --timeout 15 2>/dev/null || true
  fi
done

# Stop any stragglers
REMAINING=$(docker ps --format '{{.Names}}' | wc -l)
if [ "$REMAINING" -gt 0 ]; then
  log "[WARN] $REMAINING containers still running after stack-down"
fi

# ── Step 2: Restore backup ───────────────────────────────────
log "Restoring backup..."
tar xzf "$BACKUP_FILE" -C "$ROOT_DIR"
log "[OK] Backup restored"

# ── Step 3: Recreate networks ────────────────────────────────
log "Ensuring networks exist..."
for net in app-network db-network ai-network monitoring-network; do
  docker network create "$net" 2>/dev/null || true
done
log "[OK] Networks ready"

# ── Step 4: Start monolithic ─────────────────────────────────
log "Starting monolithic stack..."
docker compose \
  -f "$ROOT_DIR/docker-compose.yaml" \
  --env-file "$ENV_FILE" \
  -p ai-call-platform \
  up -d

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo ""
echo "═══════════════════════════════════════════════════════"
log "Rollback complete in ${ELAPSED}s"
log ""
log "Container status:"
docker ps --format "table {{.Names}}\t{{.Status}}" | head -35
echo "═══════════════════════════════════════════════════════"
