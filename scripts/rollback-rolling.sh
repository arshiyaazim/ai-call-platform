#!/usr/bin/env bash
# ============================================================
# rollback-rolling.sh — Rollback to Previous Container Version
# Usage:
#   bash scripts/rollback-rolling.sh <service-name>
#   bash scripts/rollback-rolling.sh <service-name> --dry-run
#
# Restores the previously deployed image for a service.
# Rollback info is saved automatically by deploy-rolling.sh.
# ============================================================
set -euo pipefail

SERVICE="${1:?Usage: rollback-rolling.sh <service-name> [--dry-run]}"
DRY_RUN="${2:-}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NGINX_UPSTREAM_DIR="/etc/nginx/upstreams"
STATE_DIR="/var/lib/rolling-deploy"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# ── Color output ────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[rollback]${NC} $*"; }
warn() { echo -e "${YELLOW}[rollback]${NC} $*"; }
err()  { echo -e "${RED}[rollback]${NC} $*" >&2; }

# ── Service Configuration ──────────────────────────────────
DEPLOY_METHOD=""
INTERNAL_PORT=""
BLUE_PORT=""
GREEN_PORT=""
HEALTH_PATH=""
CPU_LIMIT=""
MEM_LIMIT=""
MEM_RESERVATION=""

declare -a NETWORKS=()

get_config() {
    case "$SERVICE" in
        fazle-api)
            DEPLOY_METHOD="nginx"
            INTERNAL_PORT=8100
            BLUE_PORT=8101
            GREEN_PORT=8102
            HEALTH_PATH="/health"
            CPU_LIMIT="1"
            MEM_LIMIT="512m"
            MEM_RESERVATION="128m"
            NETWORKS=("app-network" "ai-network" "db-network")
            ;;
        fazle-brain)
            DEPLOY_METHOD="dns"
            INTERNAL_PORT=8200
            HEALTH_PATH="/health"
            CPU_LIMIT="2"
            MEM_LIMIT="1g"
            MEM_RESERVATION="256m"
            NETWORKS=("ai-network" "db-network" "app-network")
            ;;
        fazle-memory)
            DEPLOY_METHOD="dns"
            INTERNAL_PORT=8300
            HEALTH_PATH="/health"
            CPU_LIMIT="1"
            MEM_LIMIT="512m"
            MEM_RESERVATION="128m"
            NETWORKS=("ai-network" "db-network" "app-network")
            ;;
        fazle-web-intelligence)
            DEPLOY_METHOD="dns"
            INTERNAL_PORT=8500
            HEALTH_PATH="/health"
            CPU_LIMIT="0.5"
            MEM_LIMIT="512m"
            MEM_RESERVATION="128m"
            NETWORKS=("ai-network" "app-network")
            ;;
        *)
            err "Unknown service: $SERVICE"
            echo "Supported: fazle-api, fazle-brain, fazle-memory, fazle-web-intelligence"
            exit 1
            ;;
    esac
}

# ── State Helpers ───────────────────────────────────────────
get_active_slot() {
    local state_file="${STATE_DIR}/${SERVICE}.slot"
    if [ -f "$state_file" ]; then
        cat "$state_file"
    else
        echo "none"
    fi
}

set_active_slot() {
    mkdir -p "$STATE_DIR"
    echo "$1" > "${STATE_DIR}/${SERVICE}.slot"
}

# ── Health Check ────────────────────────────────────────────
wait_for_health() {
    local container_name="$1"
    local max_attempts=30
    echo -n "  Waiting for $container_name to become healthy"
    for _ in $(seq 1 "$max_attempts"); do
        local status
        status=$(docker inspect --format='{{.State.Health.Status}}' "$container_name" 2>/dev/null || echo "starting")
        if [ "$status" = "healthy" ]; then
            echo -e " ${GREEN}✓${NC}"
            return 0
        fi
        echo -n "."
        sleep 3
    done
    echo -e " ${RED}✗${NC} (timeout)"
    return 1
}

# ── Nginx Upstream Management ───────────────────────────────
update_nginx_upstream() {
    local servers="$1"
    mkdir -p "$NGINX_UPSTREAM_DIR"

    {
        echo "# Managed by rollback-rolling.sh — do not edit manually"
        echo "# Rollback at: $(date -Iseconds)"
        for port in $servers; do
            echo "server 127.0.0.1:${port};"
        done
    } > "${NGINX_UPSTREAM_DIR}/fazle-api.conf"

    nginx -t 2>&1 | sed 's/^/  /'
    nginx -s reload
    log "Nginx reloaded"
}

# ── Pre-flight Checks ──────────────────────────────────────
check_rollback_available() {
    local rollback_image_file="${STATE_DIR}/${SERVICE}.rollback-image"
    local rollback_container_file="${STATE_DIR}/${SERVICE}.rollback-container"

    if [ ! -f "$rollback_image_file" ]; then
        err "No rollback image info found at $rollback_image_file"
        err "A rolling deploy must be performed first."
        exit 1
    fi

    ROLLBACK_IMAGE=$(cat "$rollback_image_file")
    ROLLBACK_CONTAINER=$(cat "$rollback_container_file" 2>/dev/null || echo "$SERVICE")

    # Check the previous image still exists locally
    if ! docker image inspect "${SERVICE}:rolling-previous" &>/dev/null; then
        # Try the recorded image name
        if ! docker image inspect "$ROLLBACK_IMAGE" &>/dev/null; then
            err "Rollback image not found: $ROLLBACK_IMAGE"
            err "The previous image may have been pruned."
            exit 1
        fi
    else
        ROLLBACK_IMAGE="${SERVICE}:rolling-previous"
    fi

    log "Rollback image: $ROLLBACK_IMAGE"
}

# ── Rollback: Nginx Upstream Method ─────────────────────────
rollback_nginx() {
    local current_slot
    current_slot=$(get_active_slot)

    if [ "$current_slot" = "none" ]; then
        err "No rolling deployment has been performed for $SERVICE."
        err "Nothing to roll back."
        exit 1
    fi

    local current_container current_port rollback_slot rollback_port rollback_container

    case "$current_slot" in
        blue)
            current_container="${SERVICE}-blue"
            current_port=$BLUE_PORT
            rollback_slot="green"
            rollback_port=$GREEN_PORT
            rollback_container="${SERVICE}-green"
            ;;
        green)
            current_container="${SERVICE}-green"
            current_port=$GREEN_PORT
            rollback_slot="blue"
            rollback_port=$BLUE_PORT
            rollback_container="${SERVICE}-blue"
            ;;
    esac

    # Extract env from current container
    log "Extracting environment from: $current_container"
    local env_file
    env_file=$(mktemp)
    docker inspect "$current_container" \
        --format '{{range .Config.Env}}{{println .}}{{end}}' \
        > "$env_file"

    # Start rollback container with previous image
    log "Starting rollback container: $rollback_container (port $rollback_port)"
    docker rm -f "$rollback_container" 2>/dev/null || true

    docker run -d \
        --name "$rollback_container" \
        --restart unless-stopped \
        --read-only \
        --tmpfs /tmp \
        --network "${NETWORKS[0]}" \
        -p "127.0.0.1:${rollback_port}:${INTERNAL_PORT}" \
        --env-file "$env_file" \
        --log-driver json-file \
        --log-opt max-size=10m \
        --log-opt max-file=3 \
        --memory "$MEM_LIMIT" \
        --memory-reservation "$MEM_RESERVATION" \
        --cpus "$CPU_LIMIT" \
        --health-cmd "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:${INTERNAL_PORT}${HEALTH_PATH}').read()\"" \
        --health-interval 10s \
        --health-timeout 5s \
        --health-retries 3 \
        --health-start-period 30s \
        "$ROLLBACK_IMAGE"

    for net in "${NETWORKS[@]:1}"; do
        docker network connect "$net" "$rollback_container"
    done

    rm -f "$env_file"

    # Wait for health
    log "Running health check..."
    if ! wait_for_health "$rollback_container"; then
        err "Rollback container failed health check!"
        docker rm -f "$rollback_container" 2>/dev/null || true
        exit 1
    fi

    # Switch nginx upstream
    log "Switching nginx upstream to rollback container..."
    update_nginx_upstream "$rollback_port $current_port"

    # Drain
    log "Draining connections (5s)..."
    sleep 5

    # Stop current container
    log "Stopping current container: $current_container"
    docker stop "$current_container" 2>/dev/null || true
    docker rm "$current_container" 2>/dev/null || true

    # Finalize upstream
    update_nginx_upstream "$rollback_port"

    # Update state
    set_active_slot "$rollback_slot"

    log "Rollback complete: $SERVICE → $rollback_slot slot (port $rollback_port)"
    log "Image: $ROLLBACK_IMAGE"
}

# ── Rollback: Docker DNS Method ─────────────────────────────
rollback_dns() {
    local old_container="$SERVICE"
    local new_container="${SERVICE}-rollback"

    # Extract env from current container
    log "Extracting environment from: $old_container"
    local env_file
    env_file=$(mktemp)

    if docker ps --format '{{.Names}}' | grep -q "^${old_container}$"; then
        docker inspect "$old_container" \
            --format '{{range .Config.Env}}{{println .}}{{end}}' \
            > "$env_file"
    else
        err "No running container found for $SERVICE"
        rm -f "$env_file"
        exit 1
    fi

    # Start rollback container with previous image
    log "Starting rollback container: $new_container (DNS alias: $SERVICE)"
    docker rm -f "$new_container" 2>/dev/null || true

    docker run -d \
        --name "$new_container" \
        --restart unless-stopped \
        --read-only \
        --tmpfs /tmp \
        --network "${NETWORKS[0]}" \
        --network-alias "$SERVICE" \
        --env-file "$env_file" \
        --log-driver json-file \
        --log-opt max-size=10m \
        --log-opt max-file=3 \
        --memory "$MEM_LIMIT" \
        --memory-reservation "$MEM_RESERVATION" \
        --cpus "$CPU_LIMIT" \
        --health-cmd "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:${INTERNAL_PORT}${HEALTH_PATH}').read()\"" \
        --health-interval 10s \
        --health-timeout 5s \
        --health-retries 3 \
        --health-start-period 30s \
        "$ROLLBACK_IMAGE"

    for net in "${NETWORKS[@]:1}"; do
        docker network connect --alias "$SERVICE" "$net" "$new_container"
    done

    rm -f "$env_file"

    # Wait for health
    log "Running health check..."
    if ! wait_for_health "$new_container"; then
        err "Rollback container failed health check!"
        docker rm -f "$new_container" 2>/dev/null || true
        exit 1
    fi

    # Drain and swap
    log "Draining old container (3s)..."
    sleep 3

    log "Removing current container: $old_container"
    docker stop "$old_container" 2>/dev/null || true
    docker rm "$old_container" 2>/dev/null || true

    docker rename "$new_container" "$old_container"

    log "Rollback complete: $SERVICE (DNS-based)"
    log "Image: $ROLLBACK_IMAGE"
}

# ── Dry Run ─────────────────────────────────────────────────
dry_run() {
    echo ""
    echo "=== DRY RUN — No changes will be made ==="
    echo ""
    echo "Service:        $SERVICE"
    echo "Method:         $DEPLOY_METHOD"
    echo ""

    check_rollback_available

    echo ""
    echo "Rollback image: $ROLLBACK_IMAGE"
    echo ""

    if [ "$DEPLOY_METHOD" = "nginx" ]; then
        local current_slot
        current_slot=$(get_active_slot)
        echo "Current slot:   $current_slot"

        case "$current_slot" in
            blue)
                echo "Will start:     ${SERVICE}-green on port $GREEN_PORT"
                echo "Will stop:      ${SERVICE}-blue on port $BLUE_PORT"
                ;;
            green)
                echo "Will start:     ${SERVICE}-blue on port $BLUE_PORT"
                echo "Will stop:      ${SERVICE}-green on port $GREEN_PORT"
                ;;
            none)
                echo "ERROR: No rolling deploy performed yet. Nothing to rollback."
                ;;
        esac
    else
        echo "Will start:     ${SERVICE}-rollback (DNS alias: $SERVICE)"
        echo "Will stop:      ${SERVICE}"
    fi

    echo ""
    echo "Current state:"
    docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}' \
        --filter "name=${SERVICE}" 2>/dev/null || echo "  No containers found"
    echo ""
}

# ── Main ────────────────────────────────────────────────────
get_config

echo "============================================"
echo " Rollback — $SERVICE"
echo " Method: $DEPLOY_METHOD"
echo " Timestamp: $TIMESTAMP"
echo "============================================"
echo ""

if [ "$DRY_RUN" = "--dry-run" ]; then
    dry_run
    exit 0
fi

check_rollback_available

if [ "$DEPLOY_METHOD" = "nginx" ]; then
    rollback_nginx
else
    rollback_dns
fi

echo ""
echo "Verify with:"
echo "  docker ps --filter name=${SERVICE}"
echo "  docker logs --tail 20 \$(docker ps --filter name=${SERVICE} --format '{{.Names}}' | head -1)"
