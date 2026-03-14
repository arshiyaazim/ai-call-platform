#!/usr/bin/env bash
# ============================================================
# deploy-rolling.sh — Zero-Downtime Rolling Deployment
# Usage:
#   bash scripts/deploy-rolling.sh <service-name>
#   bash scripts/deploy-rolling.sh <service-name> --dry-run
#
# Supported services:
#   fazle-api            (nginx upstream method)
#   fazle-brain          (Docker DNS method)
#   fazle-memory         (Docker DNS method)
#   fazle-web-intelligence (Docker DNS method)
# ============================================================
set -euo pipefail

SERVICE="${1:?Usage: deploy-rolling.sh <service-name> [--dry-run]}"
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

log()  { echo -e "${GREEN}[rolling]${NC} $*"; }
warn() { echo -e "${YELLOW}[rolling]${NC} $*"; }
err()  { echo -e "${RED}[rolling]${NC} $*" >&2; }

# ── Service Configuration ──────────────────────────────────
# Each service defines: deploy method, ports, build context,
# health endpoint, resource limits, and network membership.
DEPLOY_METHOD=""
INTERNAL_PORT=""
BLUE_PORT=""
GREEN_PORT=""
HEALTH_PATH=""
BUILD_DIR=""
IMAGE_TAG=""
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
            BUILD_DIR="${PROJECT_DIR}/fazle-system/api"
            CPU_LIMIT="1"
            MEM_LIMIT="512m"
            MEM_RESERVATION="128m"
            NETWORKS=("app-network" "ai-network" "db-network")
            ;;
        fazle-brain)
            DEPLOY_METHOD="dns"
            INTERNAL_PORT=8200
            HEALTH_PATH="/health"
            BUILD_DIR="${PROJECT_DIR}/fazle-system/brain"
            CPU_LIMIT="2"
            MEM_LIMIT="1g"
            MEM_RESERVATION="256m"
            NETWORKS=("ai-network" "db-network" "app-network")
            ;;
        fazle-memory)
            DEPLOY_METHOD="dns"
            INTERNAL_PORT=8300
            HEALTH_PATH="/health"
            BUILD_DIR="${PROJECT_DIR}/fazle-system/memory"
            CPU_LIMIT="1"
            MEM_LIMIT="512m"
            MEM_RESERVATION="128m"
            NETWORKS=("ai-network" "db-network" "app-network")
            ;;
        fazle-web-intelligence)
            DEPLOY_METHOD="dns"
            INTERNAL_PORT=8500
            HEALTH_PATH="/health"
            BUILD_DIR="${PROJECT_DIR}/fazle-system/tools"
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

# ── State Management ────────────────────────────────────────
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

save_rollback_info() {
    local container="$1"
    mkdir -p "$STATE_DIR"
    if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        docker inspect "$container" --format '{{.Config.Image}}' \
            > "${STATE_DIR}/${SERVICE}.rollback-image"
        echo "$container" > "${STATE_DIR}/${SERVICE}.rollback-container"
        log "Rollback info saved for $container"
    fi
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
    echo -e " ${RED}✗${NC} (timeout after $((max_attempts * 3))s)"
    echo "  Last 20 lines of container logs:"
    docker logs --tail 20 "$container_name" 2>&1 | sed 's/^/    /'
    return 1
}

# ── Environment Extraction ──────────────────────────────────
# Extracts environment variables from a running container.
# This ensures rolling instances use identical configuration.
extract_env_from_container() {
    local container="$1"
    local env_file="$2"
    docker inspect "$container" \
        --format '{{range .Config.Env}}{{println .}}{{end}}' \
        > "$env_file"
}

# ── Image Build ─────────────────────────────────────────────
build_image() {
    # Preserve current image as rollback target
    if docker image inspect "${SERVICE}:rolling-latest" &>/dev/null; then
        docker tag "${SERVICE}:rolling-latest" "${SERVICE}:rolling-previous"
    fi

    IMAGE_TAG="${SERVICE}:rolling-${TIMESTAMP}"
    log "Building image: $IMAGE_TAG"
    docker build -t "$IMAGE_TAG" "$BUILD_DIR"
    docker tag "$IMAGE_TAG" "${SERVICE}:rolling-latest"
    log "Image built: $IMAGE_TAG"
}

# ── Start Container ────────────────────────────────────────
# Creates and starts a new container with the specified config.
# For nginx method: binds to a specific host port.
# For dns method: sets network aliases for Docker DNS resolution.
start_container() {
    local container_name="$1"
    local host_port="${2:-}"  # empty for DNS method
    local env_file="$3"

    # Remove stale container with same name
    docker rm -f "$container_name" 2>/dev/null || true

    local port_args=()
    if [ -n "$host_port" ]; then
        port_args=(-p "127.0.0.1:${host_port}:${INTERNAL_PORT}")
    fi

    local network_alias_args=()
    if [ "$DEPLOY_METHOD" = "dns" ]; then
        network_alias_args=(--network-alias "$SERVICE")
    fi

    docker run -d \
        --name "$container_name" \
        --restart unless-stopped \
        --read-only \
        --tmpfs /tmp \
        --network "${NETWORKS[0]}" \
        "${network_alias_args[@]}" \
        "${port_args[@]}" \
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
        "$IMAGE_TAG"

    # Connect to remaining networks
    for net in "${NETWORKS[@]:1}"; do
        if [ "$DEPLOY_METHOD" = "dns" ]; then
            docker network connect --alias "$SERVICE" "$net" "$container_name"
        else
            docker network connect "$net" "$container_name"
        fi
    done
}

# ── Nginx Upstream Management ───────────────────────────────
update_nginx_upstream() {
    local servers="$1"  # space-separated "port1 port2"
    mkdir -p "$NGINX_UPSTREAM_DIR"

    {
        echo "# Managed by deploy-rolling.sh — do not edit manually"
        echo "# Updated: $(date -Iseconds)"
        for port in $servers; do
            echo "server 127.0.0.1:${port};"
        done
    } > "${NGINX_UPSTREAM_DIR}/fazle-api.conf"

    sudo nginx -t 2>&1 | sed 's/^/  /'
    sudo nginx -s reload
    log "Nginx reloaded"
}

# ── Deploy: Nginx Upstream Method (fazle-api) ──────────────
deploy_nginx() {
    local current_slot
    current_slot=$(get_active_slot)

    local new_slot new_port old_port old_container new_container

    case "$current_slot" in
        blue)
            new_slot="green"; new_port=$GREEN_PORT; old_port=$BLUE_PORT
            old_container="${SERVICE}-blue"; new_container="${SERVICE}-green"
            ;;
        green)
            new_slot="blue"; new_port=$BLUE_PORT; old_port=$GREEN_PORT
            old_container="${SERVICE}-green"; new_container="${SERVICE}-blue"
            ;;
        none)
            # First rolling deploy — migrate from compose-managed container
            new_slot="blue"; new_port=$BLUE_PORT
            old_container="${SERVICE}"; new_container="${SERVICE}-blue"
            ;;
    esac

    # Save rollback info from current running container
    save_rollback_info "$old_container"

    # Step 1: Build
    build_image

    # Step 2: Extract env from running container
    log "Extracting environment from: $old_container"
    local env_file
    env_file=$(mktemp)

    if docker ps --format '{{.Names}}' | grep -q "^${old_container}$"; then
        extract_env_from_container "$old_container" "$env_file"
    elif [ "$current_slot" = "none" ] && docker ps --format '{{.Names}}' | grep -q "^${SERVICE}$"; then
        extract_env_from_container "$SERVICE" "$env_file"
    else
        err "No running container found for $SERVICE. Cannot extract environment."
        rm -f "$env_file"
        exit 1
    fi

    # Step 3: Start new container
    log "Starting new container: $new_container (port $new_port)"
    start_container "$new_container" "$new_port" "$env_file"
    rm -f "$env_file"
    log "Container started"

    # Step 4: Wait for health
    log "Running health check..."
    if ! wait_for_health "$new_container"; then
        err "Health check failed. Rolling back..."
        docker rm -f "$new_container" 2>/dev/null || true
        exit 1
    fi

    # Step 5: Add new container to nginx upstream (both active during transition)
    log "Adding new container to nginx upstream..."
    if [ "$current_slot" != "none" ]; then
        update_nginx_upstream "$old_port $new_port"
    else
        update_nginx_upstream "$new_port"
    fi

    # Drain connections from old container
    log "Draining connections (5s)..."
    sleep 5

    # Step 6: Remove old container from upstream and stop it
    log "Removing old container: $old_container"
    docker stop "$old_container" 2>/dev/null || true
    docker rm "$old_container" 2>/dev/null || true

    # Update upstream to only the new server
    update_nginx_upstream "$new_port"

    # Save state
    set_active_slot "$new_slot"

    echo ""
    log "Rolling deploy complete: $SERVICE"
    log "Active slot: $new_slot (port $new_port)"
}

# ── Deploy: Docker DNS Method (internal services) ──────────
deploy_dns() {
    local old_container="$SERVICE"
    local new_container="${SERVICE}-rolling"

    # Save rollback info
    save_rollback_info "$old_container"

    # Step 1: Build
    build_image

    # Step 2: Extract env from running container
    log "Extracting environment from: $old_container"
    local env_file
    env_file=$(mktemp)

    if docker ps --format '{{.Names}}' | grep -q "^${old_container}$"; then
        extract_env_from_container "$old_container" "$env_file"
    else
        err "No running container found for $SERVICE. Cannot extract environment."
        rm -f "$env_file"
        exit 1
    fi

    # Step 3: Start new container with DNS alias
    log "Starting new container: $new_container (DNS alias: $SERVICE)"
    start_container "$new_container" "" "$env_file"
    rm -f "$env_file"
    log "Container started — Docker DNS round-robin active"

    # Step 4: Wait for health
    log "Running health check..."
    if ! wait_for_health "$new_container"; then
        err "Health check failed. Rolling back..."
        docker rm -f "$new_container" 2>/dev/null || true
        exit 1
    fi

    # Brief drain period — DNS round-robin splits traffic
    log "Draining old container (3s)..."
    sleep 3

    # Step 5: Remove old container and rename new one
    log "Removing old container: $old_container"
    docker stop "$old_container" 2>/dev/null || true
    docker rm "$old_container" 2>/dev/null || true

    # Rename to original name for compose compatibility
    docker rename "$new_container" "$old_container"

    echo ""
    log "Rolling deploy complete: $SERVICE (DNS-based)"
}

# ── Dry Run ─────────────────────────────────────────────────
dry_run() {
    echo ""
    echo "=== DRY RUN — No changes will be made ==="
    echo ""
    echo "Service:        $SERVICE"
    echo "Method:         $DEPLOY_METHOD"
    echo "Internal port:  $INTERNAL_PORT"
    echo "Build dir:      $BUILD_DIR"
    echo "Networks:       ${NETWORKS[*]}"
    echo "CPU limit:      $CPU_LIMIT"
    echo "Memory limit:   $MEM_LIMIT"
    echo ""

    if [ "$DEPLOY_METHOD" = "nginx" ]; then
        local current_slot
        current_slot=$(get_active_slot)
        echo "Current slot:   $current_slot"
        echo "Blue port:      $BLUE_PORT"
        echo "Green port:     $GREEN_PORT"
        echo "Upstream file:  ${NGINX_UPSTREAM_DIR}/fazle-api.conf"
        echo ""
        echo "Steps:"
        echo "  1. Build new image from $BUILD_DIR"
        echo "  2. Extract env vars from running container"
        if [ "$current_slot" = "none" ]; then
            echo "  3. Start ${SERVICE}-blue on port $BLUE_PORT"
        elif [ "$current_slot" = "blue" ]; then
            echo "  3. Start ${SERVICE}-green on port $GREEN_PORT"
        else
            echo "  3. Start ${SERVICE}-blue on port $BLUE_PORT"
        fi
        echo "  4. Wait for health check"
        echo "  5. Update nginx upstream, reload"
        echo "  6. Drain connections (5s), stop old container"
    else
        echo "Steps:"
        echo "  1. Build new image from $BUILD_DIR"
        echo "  2. Extract env vars from running container"
        echo "  3. Start ${SERVICE}-rolling with DNS alias '$SERVICE'"
        echo "  4. Wait for health check (DNS round-robin active)"
        echo "  5. Stop old container, rename new to '$SERVICE'"
    fi

    echo ""
    echo "Current state:"
    docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' \
        --filter "name=${SERVICE}" 2>/dev/null || echo "  No containers found"
    echo ""
}

# ── Main ────────────────────────────────────────────────────
get_config

echo "============================================"
echo " Rolling Deploy — $SERVICE"
echo " Method: $DEPLOY_METHOD"
echo " Timestamp: $TIMESTAMP"
echo "============================================"
echo ""

if [ "$DRY_RUN" = "--dry-run" ]; then
    dry_run
    exit 0
fi

if [ "$DEPLOY_METHOD" = "nginx" ]; then
    deploy_nginx
else
    deploy_dns
fi

echo ""
echo "Verify with:"
echo "  docker ps --filter name=${SERVICE}"
if [ "$DEPLOY_METHOD" = "nginx" ]; then
    echo "  curl -s http://127.0.0.1:$([ "$(get_active_slot)" = "blue" ] && echo $BLUE_PORT || echo $GREEN_PORT)/health"
fi
echo "  docker logs --tail 20 \$(docker ps --filter name=${SERVICE} --format '{{.Names}}' | head -1)"
