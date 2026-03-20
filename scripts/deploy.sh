#!/usr/bin/env bash
# ============================================================
# deploy.sh — AI Voice Agent SaaS Platform Deployment
# Usage:
#   bash scripts/deploy.sh              # Full deploy
#   bash scripts/deploy.sh status       # Service status
#   bash scripts/deploy.sh restart      # Restart all services
#   bash scripts/deploy.sh update fazle # Rolling update Fazle only
#   bash scripts/deploy.sh logs [svc]   # Tail logs
# ============================================================
set -euo pipefail

DEPLOY_DIR="/home/azim/ai-call-platform"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yaml"
ACTION="${1:-deploy}"

# ── Helper functions ────────────────────────────────────────
print_status() {
    echo ""
    echo "============================================"
    echo " Service Status"
    echo "============================================"
    docker compose -f "$COMPOSE_FILE" ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    echo " Resource Usage"
    echo "============================================"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null || true
    echo ""
    echo "============================================"
    echo " Access Points"
    echo "============================================"
    echo "  Dashboard:   https://iamazim.com"
    echo "  API:         https://api.iamazim.com/api/v1/health"
    echo "  LiveKit:     wss://livekit.iamazim.com"
    echo "  TURN:        turn:turn.iamazim.com:3478"
    echo "  Fazle UI:    https://fazle.iamazim.com"
    echo "  Fazle API:   https://fazle.iamazim.com/api/fazle/health"
    echo "  Grafana:     https://iamazim.com/grafana/"
    echo "============================================"
}

wait_healthy() {
    local services=("$@")
    for svc in "${services[@]}"; do
        echo -n "  $svc: "
        for i in $(seq 1 30); do
            STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$svc" 2>/dev/null || echo "no-healthcheck")
            if [ "$STATUS" = "healthy" ]; then
                echo "✓ healthy"
                break
            elif [ "$STATUS" = "no-healthcheck" ]; then
                echo "- running (no healthcheck)"
                break
            fi
            sleep 2
        done
        if [ "$STATUS" != "healthy" ] && [ "$STATUS" != "no-healthcheck" ]; then
            echo "⚠ still $STATUS (check logs: docker logs $svc)"
        fi
    done
}

# ── Command: status ─────────────────────────────────────────
if [ "$ACTION" = "status" ]; then
    print_status
    exit 0
fi

# ── Command: logs ───────────────────────────────────────────
if [ "$ACTION" = "logs" ]; then
    SVC="${2:-}"
    if [ -n "$SVC" ]; then
        docker compose -f "$COMPOSE_FILE" logs -f --tail 100 "$SVC"
    else
        docker compose -f "$COMPOSE_FILE" logs -f --tail 50
    fi
    exit 0
fi

# ── Command: restart ────────────────────────────────────────
if [ "$ACTION" = "restart" ]; then
    echo "Restarting all services..."
    docker compose -f "$COMPOSE_FILE" restart
    sleep 5
    print_status
    exit 0
fi

# ── Command: update (rolling) ──────────────────────────────
if [ "$ACTION" = "update" ]; then
    TARGET="${2:-}"
    if [ "$TARGET" = "fazle" ]; then
        echo "Rolling update: Fazle AI System..."
        FAZLE_SERVICES="fazle-api fazle-brain fazle-memory fazle-task-engine fazle-web-intelligence fazle-trainer fazle-ui fazle-guardrail-engine"
        docker compose -f "$COMPOSE_FILE" build $FAZLE_SERVICES
        for svc in $FAZLE_SERVICES; do
            echo "  Updating $svc..."
            docker compose -f "$COMPOSE_FILE" up -d --no-deps --build "$svc"
            sleep 3
        done
        wait_healthy fazle-api fazle-brain fazle-memory fazle-task-engine fazle-web-intelligence fazle-trainer fazle-ui fazle-guardrail-engine
    elif [ "$TARGET" = "monitoring" ]; then
        echo "Updating monitoring stack..."
        docker compose -f "$COMPOSE_FILE" up -d --no-deps prometheus grafana node-exporter cadvisor loki promtail
    elif [ -n "$TARGET" ]; then
        echo "Updating service: $TARGET..."
        docker compose -f "$COMPOSE_FILE" up -d --no-deps --build "$TARGET"
        sleep 3
        wait_healthy "$TARGET"
    else
        echo "Usage: deploy.sh update [fazle|monitoring|<service-name>]"
        exit 1
    fi
    echo "Update complete."
    exit 0
fi

# ── Command: deploy (full) ─────────────────────────────────
echo "============================================"
echo " AI Voice Agent SaaS — Full Deployment"
echo "============================================"

# ── Pre-flight checks ──────────────────────────────────────
echo "[1/8] Pre-flight checks..."

if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed."
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "ERROR: Docker Compose V2 is not installed."
    exit 1
fi

if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "ERROR: .env file not found. Copy .env.example to .env and configure it."
    echo "  cp $PROJECT_DIR/.env.example $PROJECT_DIR/.env"
    exit 1
fi

# ── Create deployment directory structure ───────────────────
echo "[2/8] Setting up directory structure..."
mkdir -p "$DEPLOY_DIR"/{logs,backups}

# ── Backup existing deployment ──────────────────────────────
echo "[3/8] Backing up current state..."
BACKUP_TS=$(date +%Y%m%d_%H%M%S)
if docker compose -f "$COMPOSE_FILE" ps --quiet 2>/dev/null | head -1 > /dev/null; then
    docker compose -f "$COMPOSE_FILE" config > "$DEPLOY_DIR/backups/docker-compose-backup-$BACKUP_TS.yaml" 2>/dev/null || true
fi

# ── Validate compose file ──────────────────────────────────
echo "[4/8] Validating docker-compose.yaml..."
docker compose -f "$COMPOSE_FILE" config --quiet
echo "  ✓ Compose file is valid"

# ── Pull latest images ─────────────────────────────────────
echo "[5/8] Pulling latest images..."
docker compose -f "$COMPOSE_FILE" pull --ignore-buildable

# ── Build local services ────────────────────────────────────
echo "[6/8] Building Fazle services..."
docker compose -f "$COMPOSE_FILE" build

# ── Start services ──────────────────────────────────────────
echo "[7/8] Starting services..."
docker compose -f "$COMPOSE_FILE" up -d

# ── Wait for health checks ─────────────────────────────────
echo "[8/8] Waiting for services to become healthy..."
sleep 10

ALL_SERVICES=(
    "ai-postgres" "ai-redis" "minio" "dograh-api" "dograh-ui" "livekit"
    "qdrant" "ollama" "fazle-api" "fazle-brain" "fazle-memory"
    "fazle-task-engine" "fazle-web-intelligence" "fazle-trainer" "fazle-ui"
    "fazle-guardrail-engine"
    "prometheus" "grafana" "loki"
)
wait_healthy "${ALL_SERVICES[@]}"

# ── Summary ─────────────────────────────────────────────────
echo ""
echo "Deployment complete!"
print_status
