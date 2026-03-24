#!/bin/bash
set -e

cd /home/azim/ai-call-platform

echo "============================================================"
echo "  PHASE 3: Container Migration"
echo "============================================================"
echo ""

# ══════════════════════════════════════════════════════════════
# GROUP 1: Fazle Services
# ══════════════════════════════════════════════════════════════
echo "=== GROUP 1: Migrating Fazle services ==="
echo ""

# Stop fazle services belonging to wrong project or orphaned
echo "--- Stopping misassigned/orphaned fazle containers ---"
for c in fazle-task-engine fazle-trainer fazle-queue ai-call-platform-fazle-workers-1 ai-call-platform-fazle-workers-2 fazle-api-blue fazle-web-intelligence; do
    docker stop "$c" 2>/dev/null && echo "✓ stopped $c" || echo "⚠ $c not running"
done

echo ""
echo "--- Removing stopped containers ---"
for c in fazle-task-engine fazle-trainer fazle-queue ai-call-platform-fazle-workers-1 ai-call-platform-fazle-workers-2 fazle-api-blue fazle-web-intelligence; do
    docker rm "$c" 2>/dev/null && echo "✓ removed $c" || true
done

# Also stop/remove the existing fazle-ai containers so compose can recreate them cleanly
echo ""
echo "--- Stopping existing fazle-ai containers for clean restart ---"
cd /home/azim/ai-call-platform/fazle-ai
docker compose --env-file ../.env down 2>&1 || true

echo ""
echo "--- Starting ALL fazle services from fazle-ai compose ---"
docker compose --env-file ../.env up -d 2>&1
echo ""

echo "--- Waiting 30s for fazle services to stabilize ---"
sleep 30

echo ""
echo "--- Fazle service status ---"
docker ps --filter "name=fazle" --format "table {{.Names}}\t{{.Status}}" | sort
echo ""

# ══════════════════════════════════════════════════════════════
# GROUP 2: Dograh Services
# ══════════════════════════════════════════════════════════════
echo "=== GROUP 2: Migrating Dograh services ==="
echo ""

echo "--- Stopping dograh containers from wrong project ---"
for c in dograh-api dograh-ui livekit coturn cloudflared-tunnel; do
    docker stop "$c" 2>/dev/null && echo "✓ stopped $c" || echo "⚠ $c not running"
done

echo ""
echo "--- Removing stopped dograh containers ---"
for c in dograh-api dograh-ui livekit coturn cloudflared-tunnel; do
    docker rm "$c" 2>/dev/null && echo "✓ removed $c" || true
done

echo ""
echo "--- Starting dograh services from dograh compose ---"
cd /home/azim/ai-call-platform/dograh
docker compose -f dograh-docker-compose.yaml --env-file ../.env up -d 2>&1

echo ""
echo "--- Waiting 30s for dograh services to stabilize ---"
sleep 30

echo ""
echo "--- Dograh service status ---"
docker ps --filter "name=dograh\|livekit\|coturn\|cloudflared" --format "table {{.Names}}\t{{.Status}}" | sort
echo ""

# ══════════════════════════════════════════════════════════════
# GROUP 3: Infrastructure Services
# ══════════════════════════════════════════════════════════════
echo "=== GROUP 3: Migrating Infrastructure services ==="
echo ""

# CRITICAL: These services include databases.
# The volume names have been updated to match existing volumes.

echo "--- Stopping infrastructure containers (brief interruption) ---"
for c in prometheus grafana node-exporter cadvisor loki promtail; do
    docker stop "$c" 2>/dev/null && echo "✓ stopped $c" || echo "⚠ $c not running"
done

echo ""
echo "--- Removing stopped monitoring containers ---"
for c in prometheus grafana node-exporter cadvisor loki promtail; do
    docker rm "$c" 2>/dev/null && echo "✓ removed $c" || true
done

echo ""
echo "--- Stopping database containers (brief interruption) ---"
for c in ollama minio qdrant ai-redis ai-postgres; do
    docker stop "$c" 2>/dev/null && echo "✓ stopped $c" || echo "⚠ $c not running"
done

echo ""
echo "--- Removing stopped database containers ---"
for c in ollama minio qdrant ai-redis ai-postgres; do
    docker rm "$c" 2>/dev/null && echo "✓ removed $c" || true
done

echo ""
echo "--- Starting ALL infrastructure from ai-infra compose ---"
cd /home/azim/ai-call-platform/ai-infra
docker compose --env-file ../.env up -d 2>&1

echo ""
echo "--- Waiting 30s for infrastructure to stabilize ---"
sleep 30

echo ""
echo "--- Infrastructure service status ---"
docker ps --filter "name=postgres\|redis\|minio\|qdrant\|ollama\|prometheus\|grafana\|loki\|promtail\|cadvisor\|node-exporter" --format "table {{.Names}}\t{{.Status}}" | sort
echo ""

echo "============================================================"
echo "  PHASE 3 COMPLETE - Verifying project labels"
echo "============================================================"
echo ""

# Final verification  
bash /tmp/check-labels.sh

echo ""
echo "=== All containers ==="
docker ps --format "table {{.Names}}\t{{.Status}}" | sort
