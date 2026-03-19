#!/bin/bash
set -e

echo "============================================================"
echo "  PHASE 3: Compose Project Unification"
echo "============================================================"
echo ""

cd /home/azim/ai-call-platform

# ── Step 1: Backup compose files ──
echo "=== Step 1: Backup compose files ==="
cp ai-infra/docker-compose.yaml ai-infra/docker-compose.yaml.bak.$(date +%Y%m%d_%H%M%S)
cp dograh/dograh-docker-compose.yaml dograh/dograh-docker-compose.yaml.bak.$(date +%Y%m%d_%H%M%S)
echo "✓ Compose files backed up"
echo ""

# ── Step 2: Fix volume names in ai-infra compose to match existing volumes ──
echo "=== Step 2: Fix volume names in ai-infra/docker-compose.yaml ==="

sed -i 's/^    name: postgres_data$/    name: ai-call-platform_postgres_data/' ai-infra/docker-compose.yaml
sed -i 's/^    name: redis_data$/    name: ai-call-platform_redis_data/' ai-infra/docker-compose.yaml
sed -i 's/^    name: minio-data$/    name: ai-call-platform_minio-data/' ai-infra/docker-compose.yaml
sed -i 's/^    name: qdrant_data$/    name: ai-call-platform_qdrant_data/' ai-infra/docker-compose.yaml
sed -i 's/^    name: ollama_data$/    name: ai-call-platform_ollama_data/' ai-infra/docker-compose.yaml
sed -i 's/^    name: prometheus_data$/    name: ai-call-platform_prometheus_data/' ai-infra/docker-compose.yaml
sed -i 's/^    name: grafana_data$/    name: ai-call-platform_grafana_data/' ai-infra/docker-compose.yaml
sed -i 's/^    name: loki_data$/    name: ai-call-platform_loki_data/' ai-infra/docker-compose.yaml

echo "✓ Volume names updated to match existing volumes"

# Verify
echo "  Verify:"
grep '    name:' ai-infra/docker-compose.yaml
echo ""

# ── Step 3: Fix volume name in dograh compose ──
echo "=== Step 3: Fix volume name in dograh/dograh-docker-compose.yaml ==="
sed -i 's/^    name: shared-tmp$/    name: ai-call-platform_shared-tmp/' dograh/dograh-docker-compose.yaml
echo "✓ Dograh volume name updated"
grep '    name:' dograh/dograh-docker-compose.yaml
echo ""

# ── Step 4: Validate compose files ──
echo "=== Step 4: Validate compose files ==="
cd /home/azim/ai-call-platform/ai-infra
docker compose --env-file ../.env config > /dev/null 2>&1 && echo "✓ ai-infra compose valid" || { echo "✗ ai-infra compose INVALID"; exit 1; }

cd /home/azim/ai-call-platform/dograh
docker compose -f dograh-docker-compose.yaml --env-file ../.env config > /dev/null 2>&1 && echo "✓ dograh compose valid" || { echo "✗ dograh compose INVALID"; exit 1; }

cd /home/azim/ai-call-platform/fazle-ai
docker compose --env-file ../.env config > /dev/null 2>&1 && echo "✓ fazle-ai compose valid" || { echo "✗ fazle-ai compose INVALID"; exit 1; }
echo ""

echo "=== Step 4 COMPLETE: All compose files validated ==="
echo ""
echo "Ready for container migration."
