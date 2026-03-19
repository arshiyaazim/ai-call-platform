#!/bin/bash
set -e

cd /home/azim/ai-call-platform

echo "============================================================"
echo "  PHASE 3: Container Migration — Group 1: Fazle Services"
echo "============================================================"
echo ""

# ── Group 1A: Fazle services running under ai-call-platform project ──
# These are defined in fazle-ai/docker-compose.yaml but currently
# belong to the ai-call-platform (root) project.
# Target: fazle-task-engine, fazle-queue, fazle-trainer, fazle-workers

echo "=== Step 1: Stop fazle services running under wrong project ==="
echo "Stopping: fazle-task-engine fazle-trainer fazle-queue fazle-workers (x2)"

docker stop fazle-task-engine 2>/dev/null && echo "✓ fazle-task-engine stopped" || echo "⚠ fazle-task-engine already stopped"
docker stop fazle-trainer 2>/dev/null && echo "✓ fazle-trainer stopped" || echo "⚠ fazle-trainer already stopped"
docker stop fazle-queue 2>/dev/null && echo "✓ fazle-queue stopped" || echo "⚠ fazle-queue already stopped"
docker stop ai-call-platform-fazle-workers-1 2>/dev/null && echo "✓ fazle-workers-1 stopped" || echo "⚠ fazle-workers-1 already stopped"
docker stop ai-call-platform-fazle-workers-2 2>/dev/null && echo "✓ fazle-workers-2 stopped" || echo "⚠ fazle-workers-2 already stopped"

echo ""
echo "=== Step 2: Remove old containers ==="
docker rm fazle-task-engine 2>/dev/null && echo "✓ removed fazle-task-engine" || true
docker rm fazle-trainer 2>/dev/null && echo "✓ removed fazle-trainer" || true
docker rm fazle-queue 2>/dev/null && echo "✓ removed fazle-queue" || true
docker rm ai-call-platform-fazle-workers-1 2>/dev/null && echo "✓ removed fazle-workers-1" || true
docker rm ai-call-platform-fazle-workers-2 2>/dev/null && echo "✓ removed fazle-workers-2" || true

# ── Group 1B: Orphaned fazle containers (no project label) ──
echo ""
echo "=== Step 3: Stop orphaned fazle containers ==="
docker stop fazle-api-blue 2>/dev/null && echo "✓ fazle-api-blue stopped" || echo "⚠ fazle-api-blue already stopped"
docker stop fazle-web-intelligence 2>/dev/null && echo "✓ fazle-web-intelligence stopped" || echo "⚠ fazle-web-intelligence already stopped"

docker rm fazle-api-blue 2>/dev/null && echo "✓ removed fazle-api-blue" || true
docker rm fazle-web-intelligence 2>/dev/null && echo "✓ removed fazle-web-intelligence" || true

# ── Step 4: Restart ALL fazle services from correct compose ──
echo ""
echo "=== Step 4: Start all fazle services from fazle-ai/docker-compose.yaml ==="
cd /home/azim/ai-call-platform/fazle-ai
docker compose --env-file ../.env up -d 2>&1
echo ""

# ── Step 5: Wait for services to become healthy ──
echo "=== Step 5: Waiting for fazle services to become healthy... ==="
sleep 30

echo ""
echo "=== Fazle service status ==="
docker ps --filter "label=com.docker.compose.project=fazle-ai" --format "table {{.Names}}\t{{.Status}}" | sort
echo ""

echo "=== Step 6: Quick health check ==="
# Check a few key services
docker exec fazle-api-blue python -c "import urllib.request; print('api:', urllib.request.urlopen('http://localhost:8100/health').read().decode()[:50])" 2>/dev/null || echo "⚠ fazle-api health check pending"

echo ""
echo "=== GROUP 1 COMPLETE ==="
