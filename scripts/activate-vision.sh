#!/bin/bash
set -euo pipefail

OPENAI_KEY="${OPENAI_API_KEY:?Set OPENAI_API_KEY environment variable}"
cd /home/azim/ai-call-platform

echo "=========================================="
echo "  STEP 1: Update .env with real OpenAI key"
echo "=========================================="
# Replace placeholder (or any existing key) with real key
sed -i "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=${OPENAI_KEY}|" .env
# Verify
STORED=$(grep '^OPENAI_API_KEY=' .env | head -1)
echo "Stored: ${STORED:0:30}...${STORED: -10}"

echo ""
echo "=========================================="
echo "  STEP 2: Recreate compose-managed services"
echo "=========================================="
cd fazle-ai
docker compose --env-file ../.env up -d --no-deps fazle-memory fazle-brain fazle-learning-engine 2>&1
echo "Waiting 20s for health checks..."
sleep 20
echo "--- Service status ---"
docker ps --filter name=fazle-memory --filter name=fazle-brain --filter name=fazle-learning-engine --format 'table {{.Names}}\t{{.Status}}'
cd ..

echo ""
echo "=========================================="
echo "  STEP 3: Recreate fazle-api-blue"
echo "=========================================="
# Stop old blue
echo "Stopping old fazle-api-blue..."
docker stop fazle-api-blue 2>/dev/null || true
docker rm fazle-api-blue 2>/dev/null || true

# Collect env vars from compose env-file + override the key
# Write a clean env file for the blue container
cat > /tmp/fazle-api-blue.env << ENVEOF
FAZLE_API_KEY=2aMFFfIaGDfgfP6JiXaevEgMRx9aZtgAzYriHGRcpvdEcWCtp7Xpqul0BYdjFchq
FAZLE_BRAIN_URL=http://fazle-brain:8200
FAZLE_DATABASE_URL=postgresql://postgres:3UTioVfpNwVgcZ2VtlEr9XDR5C8PSOb@postgres:5432/postgres
FAZLE_JWT_SECRET=HA2BbYBlWuWeEFjBlCJohV5Q52sqSuHiz3vTxxuSF5dY9Dhb
FAZLE_LEARNING_ENGINE_URL=http://fazle-learning-engine:8900
FAZLE_LIVEKIT_API_KEY=API88f0aec95c61
FAZLE_LIVEKIT_API_SECRET=tvHZFR0IImCbKcDgi19rRrqTMXCTzKiKrRzL1SkQqqc2nakB
FAZLE_LIVEKIT_URL=wss://livekit.iamazim.com
FAZLE_MEMORY_URL=http://fazle-memory:8300
FAZLE_MINIO_ACCESS_KEY=minioadmin
FAZLE_MINIO_BUCKET=fazle-multimodal
FAZLE_MINIO_ENDPOINT=minio:9000
FAZLE_MINIO_SECRET_KEY=vxzTY3DP35ihRRv0C0uCQCmY2jdNBsw
FAZLE_OPENAI_API_KEY=${OPENAI_KEY}
FAZLE_TASK_URL=http://fazle-task-engine:8400
FAZLE_TOOLS_URL=http://fazle-web-intelligence:8500
FAZLE_TRAINER_URL=http://fazle-trainer:8600
ENVEOF

echo "Starting new fazle-api-blue..."
docker run -d \
  --name fazle-api-blue \
  --env-file /tmp/fazle-api-blue.env \
  --publish 127.0.0.1:8101:8100 \
  --read-only \
  --tmpfs /tmp \
  --memory 536870912 \
  --restart unless-stopped \
  --health-cmd 'python -c "import urllib.request; urllib.request.urlopen('"'"'http://localhost:8100/health'"'"').read()"' \
  --health-interval 10s \
  --health-timeout 5s \
  --health-start-period 30s \
  --health-retries 3 \
  fazle-ai-fazle-api:latest

echo "Waiting 15s for blue container health..."
sleep 15
docker ps --filter name=fazle-api-blue --format 'table {{.Names}}\t{{.Status}}'

echo ""
echo "=========================================="
echo "  STEP 4: Fix networking + alias"
echo "=========================================="
/home/azim/ai-call-platform/scripts/fix-fazle-api-network.sh

echo ""
echo "=========================================="
echo "  STEP 5: Verify nginx still routes to blue"
echo "=========================================="
cat /etc/nginx/upstreams/fazle-api.conf
curl -s http://127.0.0.1:8101/health

echo ""
echo "=========================================="
echo "  STEP 6: Verify OpenAI key in all services"
echo "=========================================="
echo -n "fazle-memory: "
docker exec fazle-memory env | grep OPENAI_API_KEY | cut -c1-35
echo -n "fazle-brain: "
docker exec fazle-brain env | grep FAZLE_OPENAI_API_KEY | cut -c1-40
echo -n "fazle-api-blue: "
docker exec fazle-api-blue env | grep FAZLE_OPENAI_API_KEY | cut -c1-40
echo -n "fazle-llm-gateway: "
docker exec fazle-llm-gateway env | grep OPENAI_API_KEY | cut -c1-35

echo ""
echo "=========================================="
echo "  STEP 7: Verify all fazle services"
echo "=========================================="
docker ps --format 'table {{.Names}}\t{{.Status}}' | grep fazle | sort

echo ""
echo "=========================================="
echo "  STEP 8: Test multimodal embedding"
echo "=========================================="
# Test from memory container - try a simple multimodal search
docker exec -i fazle-memory python3 - << 'PYTEST'
import httpx, json, os
key = os.environ.get("OPENAI_API_KEY", "")
print(f"Key present: {len(key)} chars, starts with: {key[:20]}...")
# Quick embedding test
try:
    r = httpx.post(
        "https://api.openai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": "text-embedding-3-large", "input": "test vision activation"},
        timeout=15
    )
    if r.status_code == 200:
        dims = len(r.json()["data"][0]["embedding"])
        print(f"EMBEDDING OK — {dims} dimensions returned")
    else:
        print(f"EMBEDDING FAIL — {r.status_code}: {r.text[:200]}")
except Exception as e:
    print(f"EMBEDDING ERROR: {e}")
PYTEST

# Clean up env file
rm -f /tmp/fazle-api-blue.env

echo ""
echo "════════════════════════════════════════════════════════════"
echo "                  ACTIVATION COMPLETE"
echo "════════════════════════════════════════════════════════════"
