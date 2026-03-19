#!/usr/bin/env bash
set -euo pipefail

# Blue-green deploy for fazle-api
# Current: GREEN on port 8102
# Target:  BLUE on port 8101

ENV_FILE="/home/azim/ai-call-platform/.env"

echo "=== Phase 1: Image already built ==="

echo "=== Phase 2: Collect env vars ==="
# Get env vars from running green container, write to a temp env file
docker exec fazle-api-green env | grep -v '^PATH=\|^HOME=\|^HOSTNAME=\|^LANG=\|^GPG_KEY=\|^PYTHON_\|^VIRTUAL_ENV=' > /tmp/fazle-api-blue.env

# Add new multimodal env vars from .env
AK=$(sed 's/\r$//' "$ENV_FILE" | grep '^MINIO_ACCESS_KEY=' | cut -d= -f2)
SK=$(sed 's/\r$//' "$ENV_FILE" | grep '^MINIO_SECRET_KEY=' | cut -d= -f2)
OAK=$(sed 's/\r$//' "$ENV_FILE" | grep '^OPENAI_API_KEY=' | cut -d= -f2)

echo "FAZLE_OPENAI_API_KEY=$OAK" >> /tmp/fazle-api-blue.env
echo "FAZLE_MINIO_ENDPOINT=minio:9000" >> /tmp/fazle-api-blue.env
echo "FAZLE_MINIO_ACCESS_KEY=$AK" >> /tmp/fazle-api-blue.env
echo "FAZLE_MINIO_SECRET_KEY=$SK" >> /tmp/fazle-api-blue.env
echo "FAZLE_MINIO_BUCKET=fazle-multimodal" >> /tmp/fazle-api-blue.env

echo "  Env vars collected: $(wc -l < /tmp/fazle-api-blue.env) total"

echo "=== Phase 3: Start BLUE container on port 8101 ==="
docker rm -f fazle-api-blue 2>/dev/null || true

docker run -d \
  --name fazle-api-blue \
  --read-only \
  --tmpfs /tmp \
  -m 536870912 \
  --restart unless-stopped \
  -p 127.0.0.1:8101:8100 \
  --health-cmd 'python -c "import urllib.request; urllib.request.urlopen('"'"'http://localhost:8100/health'"'"').read()"' \
  --health-interval 10s \
  --health-timeout 5s \
  --health-start-period 30s \
  --health-retries 3 \
  --env-file /tmp/fazle-api-blue.env \
  fazle-ai-fazle-api:latest

echo "Connecting to networks..."
docker network connect ai-network fazle-api-blue 2>/dev/null || true
docker network connect db-network fazle-api-blue 2>/dev/null || true

echo "=== Phase 4: Wait for BLUE to become healthy ==="
for i in $(seq 1 30); do
  STATUS=$(docker inspect fazle-api-blue --format '{{.State.Health.Status}}' 2>/dev/null || echo "unknown")
  echo "  Attempt $i/30: $STATUS"
  if [ "$STATUS" = "healthy" ]; then
    break
  fi
  sleep 5
done

FINAL_STATUS=$(docker inspect fazle-api-blue --format '{{.State.Health.Status}}' 2>/dev/null || echo "unknown")
if [ "$FINAL_STATUS" != "healthy" ]; then
  echo "ERROR: BLUE container did not become healthy. Aborting."
  echo "Logs:"
  docker logs fazle-api-blue --tail 30
  docker rm -f fazle-api-blue
  exit 1
fi

echo "=== Phase 5: Swap nginx upstream to BLUE (port 8101) ==="
echo 'server 127.0.0.1:8101;' | sudo tee /etc/nginx/upstreams/fazle-api.conf > /dev/null
sudo nginx -t && sudo nginx -s reload
echo "Nginx reloaded."

echo "=== Phase 6: Stop GREEN container ==="
sleep 3
docker stop fazle-api-green
docker rm fazle-api-green
echo "GREEN removed."

echo "=== Phase 7: Update state file ==="
echo "blue" | sudo tee /var/lib/rolling-deploy/fazle-api.slot > /dev/null

# Cleanup
rm -f /tmp/fazle-api-blue.env

echo "=== BLUE-GREEN DEPLOY COMPLETE ==="
echo "Active slot: BLUE (port 8101)"
docker ps --filter name=fazle-api-blue --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
