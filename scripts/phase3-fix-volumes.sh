#!/bin/bash
set -e

cd /home/azim/ai-call-platform

echo "=== Fixing line endings and volume names ==="

# Convert to Unix line endings first
sed -i 's/\r$//' ai-infra/docker-compose.yaml
sed -i 's/\r$//' dograh/dograh-docker-compose.yaml
echo "✓ Line endings fixed"

# Now fix volume names in ai-infra
sed -i 's/^    name: postgres_data$/    name: ai-call-platform_postgres_data/' ai-infra/docker-compose.yaml
sed -i 's/^    name: redis_data$/    name: ai-call-platform_redis_data/' ai-infra/docker-compose.yaml
sed -i 's/^    name: minio-data$/    name: ai-call-platform_minio-data/' ai-infra/docker-compose.yaml
sed -i 's/^    name: qdrant_data$/    name: ai-call-platform_qdrant_data/' ai-infra/docker-compose.yaml
sed -i 's/^    name: ollama_data$/    name: ai-call-platform_ollama_data/' ai-infra/docker-compose.yaml
sed -i 's/^    name: prometheus_data$/    name: ai-call-platform_prometheus_data/' ai-infra/docker-compose.yaml
sed -i 's/^    name: grafana_data$/    name: ai-call-platform_grafana_data/' ai-infra/docker-compose.yaml
sed -i 's/^    name: loki_data$/    name: ai-call-platform_loki_data/' ai-infra/docker-compose.yaml

# Fix volume name in dograh
sed -i 's/^    name: shared-tmp$/    name: ai-call-platform_shared-tmp/' dograh/dograh-docker-compose.yaml

echo ""
echo "=== Verify ai-infra volume names ==="
grep '    name:' ai-infra/docker-compose.yaml | grep -v container_name

echo ""
echo "=== Verify dograh volume names ==="
grep '    name:' dograh/dograh-docker-compose.yaml | grep -v container_name

echo ""
echo "=== Validate compose files ==="
cd /home/azim/ai-call-platform/ai-infra && docker compose --env-file ../.env config > /dev/null 2>&1 && echo "✓ ai-infra valid" || echo "✗ ai-infra INVALID"
cd /home/azim/ai-call-platform/dograh && docker compose -f dograh-docker-compose.yaml --env-file ../.env config > /dev/null 2>&1 && echo "✓ dograh valid" || echo "✗ dograh INVALID"
cd /home/azim/ai-call-platform/fazle-ai && docker compose --env-file ../.env config > /dev/null 2>&1 && echo "✓ fazle-ai valid" || echo "✗ fazle-ai INVALID"

echo ""
echo "=== DONE ==="
