#!/bin/bash
# ============================================================
# GitOps Auto-Deploy Script — AI Call Platform
# Pulls latest code, detects changes, rebuilds only affected stacks
# ============================================================
set -euo pipefail

PROJECT_ROOT="/home/azim/ai-call-platform"
ENV_FILE="${PROJECT_ROOT}/.env"
DEPLOY_LOG="/var/log/gitops-deploy.log"
LOCK_FILE="/tmp/gitops-deploy.lock"

# ── Logging ──────────────────────────────────────────────────
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$DEPLOY_LOG"; }
err() { log "ERROR: $*"; }

# ── Lock — prevent concurrent deployments ────────────────────
cleanup() { rm -f "$LOCK_FILE"; }
trap cleanup EXIT

if [ -f "$LOCK_FILE" ]; then
    pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        err "Another deployment is running (PID $pid). Aborting."
        exit 1
    fi
    log "Stale lock file found — removing."
fi
echo $$ > "$LOCK_FILE"

# ── Pre-flight ───────────────────────────────────────────────
log "========== GitOps Deployment Starting =========="
cd "$PROJECT_ROOT"

if [ ! -f "$ENV_FILE" ]; then
    err ".env file missing — aborting deployment."
    exit 1
fi

# ── Pull latest code ─────────────────────────────────────────
log "Pulling latest code from origin..."
BEFORE_HASH=$(git rev-parse HEAD)
git pull origin main --ff-only 2>&1 | tee -a "$DEPLOY_LOG"
AFTER_HASH=$(git rev-parse HEAD)

if [ "$BEFORE_HASH" = "$AFTER_HASH" ]; then
    log "No new commits — nothing to deploy."
    exit 0
fi

log "Deploying: ${BEFORE_HASH:0:8} → ${AFTER_HASH:0:8}"

# ── Detect changed files ─────────────────────────────────────
CHANGED_FILES=$(git diff --name-only "$BEFORE_HASH" "$AFTER_HASH")
log "Changed files:\n$CHANGED_FILES"

# ── Map changes to stacks ────────────────────────────────────
DEPLOY_ROOT=false
DEPLOY_AI_INFRA=false
DEPLOY_FAZLE=false
DEPLOY_DOGRAH=false
DEPLOY_WATCHDOG=false
DEPLOY_CONTROL_PLANE=false

while IFS= read -r file; do
    case "$file" in
        ai-infra/*)          DEPLOY_AI_INFRA=true ;;
        fazle-ai/*|fazle-system/*) DEPLOY_FAZLE=true ;;
        dograh/*)            DEPLOY_DOGRAH=true ;;
        ai-watchdog/*)       DEPLOY_WATCHDOG=true ;;
        ai-control-plane/*)  DEPLOY_CONTROL_PLANE=true ;;
        docker-compose.yaml) DEPLOY_ROOT=true ;;
        configs/*)           DEPLOY_ROOT=true; DEPLOY_AI_INFRA=true ;;
    esac
done <<< "$CHANGED_FILES"

# ── Deploy function ──────────────────────────────────────────
deploy_stack() {
    local name="$1"
    local dir="$2"
    local compose_file="${3:-docker-compose.yaml}"

    log "  Deploying stack: $name ($dir/$compose_file)"

    cd "$PROJECT_ROOT/$dir"
    docker compose -f "$compose_file" --env-file "$ENV_FILE" build 2>&1 | tail -5 | tee -a "$DEPLOY_LOG"
    docker compose -f "$compose_file" --env-file "$ENV_FILE" up -d 2>&1 | tee -a "$DEPLOY_LOG"
    cd "$PROJECT_ROOT"
}

# ── Execute deployments (order matters: infra first) ─────────
DEPLOYED=0

if [ "$DEPLOY_AI_INFRA" = true ]; then
    log "Stack changed: ai-infra"
    deploy_stack "ai-infra" "ai-infra"
    DEPLOYED=$((DEPLOYED + 1))
fi

if [ "$DEPLOY_ROOT" = true ]; then
    log "Stack changed: root (base services)"
    deploy_stack "root" "."
    DEPLOYED=$((DEPLOYED + 1))
fi

if [ "$DEPLOY_FAZLE" = true ]; then
    log "Stack changed: fazle-ai"
    deploy_stack "fazle-ai" "fazle-ai"
    DEPLOYED=$((DEPLOYED + 1))
fi

if [ "$DEPLOY_DOGRAH" = true ]; then
    log "Stack changed: dograh"
    deploy_stack "dograh" "dograh" "dograh-docker-compose.yaml"
    DEPLOYED=$((DEPLOYED + 1))
fi

if [ "$DEPLOY_WATCHDOG" = true ]; then
    log "Stack changed: ai-watchdog"
    deploy_stack "ai-watchdog" "ai-watchdog"
    DEPLOYED=$((DEPLOYED + 1))
fi

if [ "$DEPLOY_CONTROL_PLANE" = true ]; then
    log "Stack changed: ai-control-plane"
    deploy_stack "ai-control-plane" "ai-control-plane"
    DEPLOYED=$((DEPLOYED + 1))
fi

# ── Health check ─────────────────────────────────────────────
log "Waiting 30s for containers to stabilize..."
sleep 30

UNHEALTHY=$(docker ps --filter health=unhealthy --format '{{.Names}}' 2>/dev/null)
EXITED=$(docker ps -a --filter status=exited --format '{{.Names}}' 2>/dev/null | grep -E 'fazle|dograh|ai-' || true)

if [ -n "$UNHEALTHY" ]; then
    log "WARNING: Unhealthy containers detected: $UNHEALTHY"
fi

if [ -n "$EXITED" ]; then
    log "WARNING: Exited containers detected: $EXITED"
fi

RUNNING=$(docker ps --format '{{.Names}}' | wc -l)
log "========== Deployment Complete =========="
log "Stacks deployed: $DEPLOYED"
log "Running containers: $RUNNING"
log "Commit: ${AFTER_HASH:0:8}"

exit 0
