#!/usr/bin/env bash
# ============================================================
# Migration Deploy Script — Split Compose Stacks
# Safely migrates from single docker-compose.yaml to three
# separate stacks: ai-infra, dograh, fazle-ai
# ============================================================
# Usage: bash migration-deploy.sh [--dry-run]
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY_RUN=false

if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "=== DRY RUN MODE — No changes will be made ==="
fi

# ── Color output ─────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; }
info() { echo -e "${BLUE}[INFO]${NC} $1"; }

# ── Pre-flight checks ───────────────────────────────────────
echo ""
echo "============================================================"
echo "  Migration: Single Compose → Three-Stack Architecture"
echo "============================================================"
echo ""

# Check Docker is running
if ! docker info > /dev/null 2>&1; then
    err "Docker is not running. Please start Docker first."
    exit 1
fi

# Check compose files exist
for f in \
    "$SCRIPT_DIR/ai-infra/docker-compose.yaml" \
    "$SCRIPT_DIR/dograh/dograh-docker-compose.yaml" \
    "$SCRIPT_DIR/fazle-ai/fazle-docker-compose.yaml"; do
    if [[ ! -f "$f" ]]; then
        err "Missing compose file: $f"
        exit 1
    fi
done

# Check .env file exists
if [[ ! -f "$SCRIPT_DIR/.env" ]] && [[ ! -f "$SCRIPT_DIR/.env.local" ]]; then
    err "No .env or .env.local file found in $SCRIPT_DIR"
    err "Create one from .env.example before running migration."
    exit 1
fi

ENV_FILE="$SCRIPT_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
    ENV_FILE="$SCRIPT_DIR/.env.local"
fi

log "Pre-flight checks passed"
echo ""

# ============================================================
# STEP 1 — Create External Networks
# ============================================================
info "Step 1: Creating external Docker networks..."

create_network() {
    local name="$1"
    local flags="${2:-}"

    if docker network inspect "$name" > /dev/null 2>&1; then
        warn "Network '$name' already exists — skipping"
    else
        if [[ "$DRY_RUN" == true ]]; then
            info "[DRY RUN] Would create network: $name $flags"
        else
            docker network create --driver bridge $flags "$name"
            log "Created network: $name"
        fi
    fi
}

create_network "app-network"
create_network "db-network"     "--internal"
create_network "ai-network"     "--internal"
create_network "monitoring-network" "--internal"

echo ""

# ============================================================
# STEP 2 — Detect and Migrate Volumes
# ============================================================
info "Step 2: Checking volume migration..."

# REVIEW_REQUIRED: The old compose may have created volumes with
# a project-name prefix (e.g., "vps-deploy_postgres_data").
# This script detects old volumes and migrates data to the new
# explicitly-named volumes.

# List of volumes used by the new compose files
VOLUMES=(
    "postgres_data"
    "redis_data"
    "minio-data"
    "qdrant_data"
    "ollama_data"
    "prometheus_data"
    "grafana_data"
    "loki_data"
    "shared-tmp"
)

# Auto-detect the old project name by checking existing volumes
OLD_PROJECT=""
for candidate in $(docker volume ls --format '{{.Name}}' | grep '_postgres_data$' | sed 's/_postgres_data$//'); do
    OLD_PROJECT="$candidate"
    break
done

if [[ -n "$OLD_PROJECT" ]]; then
    info "Detected old project name: '$OLD_PROJECT'"
    echo ""

    for vol in "${VOLUMES[@]}"; do
        old_vol="${OLD_PROJECT}_${vol}"
        new_vol="$vol"

        if docker volume inspect "$old_vol" > /dev/null 2>&1; then
            if docker volume inspect "$new_vol" > /dev/null 2>&1; then
                warn "Both '$old_vol' and '$new_vol' exist — skipping (manual review needed)"
            else
                if [[ "$DRY_RUN" == true ]]; then
                    info "[DRY RUN] Would migrate volume: $old_vol → $new_vol"
                else
                    info "Migrating volume: $old_vol → $new_vol"
                    docker volume create "$new_vol"
                    docker run --rm \
                        -v "${old_vol}:/from:ro" \
                        -v "${new_vol}:/to" \
                        alpine sh -c 'cp -a /from/. /to/'
                    log "Migrated: $old_vol → $new_vol"
                fi
            fi
        else
            if docker volume inspect "$new_vol" > /dev/null 2>&1; then
                log "Volume '$new_vol' already exists"
            else
                info "Volume '$old_vol' not found (may not have been created yet)"
            fi
        fi
    done
else
    info "No project-prefixed volumes detected."
    info "Volumes will be created automatically by docker compose."
fi

echo ""

# ============================================================
# STEP 3 — Symlink .env to subdirectories
# ============================================================
info "Step 3: Symlinking .env file to stack directories..."

for subdir in ai-infra dograh fazle-ai; do
    target="$SCRIPT_DIR/$subdir/.env"
    if [[ -f "$target" ]] || [[ -L "$target" ]]; then
        warn "$subdir/.env already exists — skipping"
    else
        if [[ "$DRY_RUN" == true ]]; then
            info "[DRY RUN] Would symlink: $ENV_FILE → $target"
        else
            ln -sf "$ENV_FILE" "$target"
            log "Symlinked .env → $subdir/.env"
        fi
    fi
done

echo ""

# ============================================================
# STEP 4 — Stop Old Compose (if running)
# ============================================================
info "Step 4: Checking for running old compose stack..."

if docker compose -f "$SCRIPT_DIR/docker-compose.yaml" ps --quiet 2>/dev/null | head -1 | grep -q .; then
    warn "Old compose stack is running."
    echo ""
    echo "  To proceed, the old stack must be stopped."
    echo "  This will cause a brief downtime."
    echo ""
    read -p "  Stop the old stack now? (y/N) " -r REPLY
    echo ""
    if [[ "$REPLY" =~ ^[Yy]$ ]]; then
        if [[ "$DRY_RUN" == true ]]; then
            info "[DRY RUN] Would run: docker compose -f docker-compose.yaml down"
        else
            info "Stopping old compose stack..."
            docker compose -f "$SCRIPT_DIR/docker-compose.yaml" down
            log "Old stack stopped. Volumes preserved."
        fi
    else
        warn "Old stack not stopped. Cannot proceed with new stack deployment."
        warn "Stop the old stack first: docker compose -f docker-compose.yaml down"
        exit 1
    fi
else
    log "No running old compose stack detected"
fi

echo ""

# ============================================================
# STEP 5 — Deploy New Stacks (in order)
# ============================================================
info "Step 5: Deploying new stacks..."
echo ""

# Stack 1: Infrastructure
info "  [1/3] Starting ai-infra stack..."
if [[ "$DRY_RUN" == true ]]; then
    info "  [DRY RUN] Would run: docker compose -f ai-infra/docker-compose.yaml up -d"
else
    cd "$SCRIPT_DIR/ai-infra"
    docker compose up -d
    log "  ai-infra stack started"
fi

echo ""
info "  Waiting for infrastructure to become healthy..."
if [[ "$DRY_RUN" == false ]]; then
    # Wait for postgres and redis to be healthy (up to 60s)
    TIMEOUT=60
    ELAPSED=0
    while [[ $ELAPSED -lt $TIMEOUT ]]; do
        PG_HEALTHY=$(docker inspect --format='{{.State.Health.Status}}' ai-postgres 2>/dev/null || echo "starting")
        RD_HEALTHY=$(docker inspect --format='{{.State.Health.Status}}' ai-redis 2>/dev/null || echo "starting")
        if [[ "$PG_HEALTHY" == "healthy" ]] && [[ "$RD_HEALTHY" == "healthy" ]]; then
            log "  PostgreSQL and Redis are healthy"
            break
        fi
        sleep 2
        ELAPSED=$((ELAPSED + 2))
    done
    if [[ $ELAPSED -ge $TIMEOUT ]]; then
        warn "  Timed out waiting for infrastructure health. Continuing anyway..."
    fi
fi

echo ""

# Stack 2: Dograh
info "  [2/3] Starting dograh stack..."
if [[ "$DRY_RUN" == true ]]; then
    info "  [DRY RUN] Would run: docker compose -f dograh/dograh-docker-compose.yaml up -d"
else
    cd "$SCRIPT_DIR/dograh"
    docker compose -f dograh-docker-compose.yaml up -d
    log "  dograh stack started"
fi

echo ""

# Stack 3: Fazle AI
info "  [3/3] Starting fazle-ai stack..."
if [[ "$DRY_RUN" == true ]]; then
    info "  [DRY RUN] Would run: docker compose -f fazle-ai/fazle-docker-compose.yaml up -d"
else
    cd "$SCRIPT_DIR/fazle-ai"
    docker compose -f fazle-docker-compose.yaml up -d
    log "  fazle-ai stack started"
fi

echo ""

# ============================================================
# STEP 6 — Verify All Services
# ============================================================
info "Step 6: Verifying services..."
echo ""

if [[ "$DRY_RUN" == true ]]; then
    info "[DRY RUN] Would verify all container health"
else
    # Wait a moment for services to start
    sleep 10

    EXPECTED_CONTAINERS=(
        "ai-postgres"
        "ai-redis"
        "minio"
        "qdrant"
        "ollama"
        "prometheus"
        "grafana"
        "node-exporter"
        "cadvisor"
        "loki"
        "promtail"
        "livekit"
        "coturn"
        "dograh-api"
        "dograh-ui"
        "cloudflared-tunnel"
        "fazle-api"
        "fazle-brain"
        "fazle-memory"
        "fazle-task-engine"
        "fazle-web-intelligence"
        "fazle-trainer"
        "fazle-voice"
        "fazle-ui"
    )

    ALL_OK=true
    for cname in "${EXPECTED_CONTAINERS[@]}"; do
        STATUS=$(docker inspect --format='{{.State.Status}}' "$cname" 2>/dev/null || echo "missing")
        HEALTH=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "$cname" 2>/dev/null || echo "unknown")
        if [[ "$STATUS" == "running" ]]; then
            log "  $cname: running (health: $HEALTH)"
        else
            err "  $cname: $STATUS"
            ALL_OK=false
        fi
    done

    echo ""
    if [[ "$ALL_OK" == true ]]; then
        log "All containers are running!"
    else
        warn "Some containers are not running. Check logs with:"
        echo "  docker logs <container_name>"
    fi
fi

echo ""

# ============================================================
# STEP 7 — Cross-Stack Connectivity Check
# ============================================================
info "Step 7: Testing cross-stack connectivity..."

if [[ "$DRY_RUN" == true ]]; then
    info "[DRY RUN] Would test cross-stack DNS and connectivity"
else
    # Test: Fazle API → PostgreSQL (cross-compose via db-network)
    if docker exec fazle-api python -c "
import urllib.request
urllib.request.urlopen('http://localhost:8100/health').read()
" > /dev/null 2>&1; then
        log "  Fazle API health check passed"
    else
        warn "  Fazle API health check failed (may still be starting)"
    fi

    # Test: Dograh API → health
    if docker exec dograh-api python -c "
import urllib.request
urllib.request.urlopen('http://localhost:8000/api/v1/health').read()
" > /dev/null 2>&1; then
        log "  Dograh API health check passed"
    else
        warn "  Dograh API health check failed (may still be starting)"
    fi

    # Test DNS resolution across compose boundaries
    if docker exec fazle-brain python -c "
import socket
socket.getaddrinfo('redis', 6379)
" > /dev/null 2>&1; then
        log "  Cross-stack DNS: fazle-brain → redis OK"
    else
        warn "  Cross-stack DNS: fazle-brain → redis FAILED"
    fi

    if docker exec fazle-brain python -c "
import socket
socket.getaddrinfo('ollama', 11434)
" > /dev/null 2>&1; then
        log "  Cross-stack DNS: fazle-brain → ollama OK"
    else
        warn "  Cross-stack DNS: fazle-brain → ollama FAILED"
    fi

    if docker exec fazle-memory python -c "
import socket
socket.getaddrinfo('qdrant', 6333)
" > /dev/null 2>&1; then
        log "  Cross-stack DNS: fazle-memory → qdrant OK"
    else
        warn "  Cross-stack DNS: fazle-memory → qdrant FAILED"
    fi
fi

echo ""
echo "============================================================"
if [[ "$DRY_RUN" == true ]]; then
    info "DRY RUN COMPLETE — No changes were made"
else
    log "MIGRATION COMPLETE"
    echo ""
    echo "  The original docker-compose.yaml has NOT been modified."
    echo "  It remains available as a fallback."
    echo ""
    echo "  To rollback:"
    echo "    cd ai-infra  && docker compose down"
    echo "    cd ../dograh && docker compose -f dograh-docker-compose.yaml down"
    echo "    cd ../fazle-ai && docker compose -f fazle-docker-compose.yaml down"
    echo "    cd .. && docker compose up -d"
fi
echo "============================================================"
