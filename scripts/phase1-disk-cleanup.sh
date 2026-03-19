#!/bin/bash
set -e

echo "=== PHASE 1: Disk Cleanup - Rolling & Unused Images ==="
echo ""

# Record disk before
DISK_BEFORE=$(df -h / | tail -1 | awk '{print $3}')
echo "Disk usage BEFORE: $DISK_BEFORE"
echo ""

# SAFE: Remove old rolling images NOT in use by any running container
echo "--- Removing old rolling images ---"

# fazle-memory rolling (12.4 GB!) - NOT in use
docker rmi fazle-memory:rolling-20260313_235603 2>/dev/null && echo "✓ Removed fazle-memory:rolling-20260313_235603" || echo "⚠ fazle-memory:rolling-20260313_235603 not found"

# fazle-api old rolling tags - NOT in use
docker rmi fazle-api:rolling-20260313_234726 2>/dev/null && echo "✓ Removed fazle-api:rolling-20260313_234726" || echo "⚠ fazle-api:rolling-20260313_234726 not found"
docker rmi fazle-api:rolling-persona-evo 2>/dev/null && echo "✓ Removed fazle-api:rolling-persona-evo" || echo "⚠ fazle-api:rolling-persona-evo not found"
docker rmi fazle-api:rolling-previous 2>/dev/null && echo "✓ Removed fazle-api:rolling-previous" || echo "⚠ fazle-api:rolling-previous not found"
docker rmi fazle-api:rolling-20260316_224627 2>/dev/null && echo "✓ Removed fazle-api:rolling-20260316_224627" || echo "⚠ fazle-api:rolling-20260316_224627 not found"

# KEEP: fazle-api:rolling-20260316_224817 / rolling-latest (used by fazle-api-blue)
# KEEP: fazle-web-intelligence:rolling-20260314_001810 (used by fazle-web-intelligence)

echo ""
echo "--- Removing old multimodal image ---"
docker rmi fazle-ai-fazle-memory:multimodal 2>/dev/null && echo "✓ Removed fazle-ai-fazle-memory:multimodal" || echo "⚠ fazle-ai-fazle-memory:multimodal not found"

echo ""
echo "--- Removing old root-compose images NOT in use ---"

# These ai-call-platform-* images are NOT used by running containers
# (brain, learning-engine, llm-gateway, ui, voice all use fazle-ai-* versions)
docker rmi ai-call-platform-fazle-brain:latest 2>/dev/null && echo "✓ Removed ai-call-platform-fazle-brain:latest" || echo "⚠ ai-call-platform-fazle-brain:latest not found"
docker rmi ai-call-platform-fazle-learning-engine:latest 2>/dev/null && echo "✓ Removed ai-call-platform-fazle-learning-engine:latest" || echo "⚠ ai-call-platform-fazle-learning-engine:latest not found"
docker rmi ai-call-platform-fazle-llm-gateway:latest 2>/dev/null && echo "✓ Removed ai-call-platform-fazle-llm-gateway:latest" || echo "⚠ ai-call-platform-fazle-llm-gateway:latest not found"
docker rmi ai-call-platform-fazle-ui:latest 2>/dev/null && echo "✓ Removed ai-call-platform-fazle-ui:latest" || echo "⚠ ai-call-platform-fazle-ui:latest not found"
docker rmi ai-call-platform-fazle-voice:latest 2>/dev/null && echo "✓ Removed ai-call-platform-fazle-voice:latest" || echo "⚠ ai-call-platform-fazle-voice:latest not found"

# fazle-ai-fazle-api:latest is NOT the one used by fazle-api-blue (that uses rolling tag)
docker rmi fazle-ai-fazle-api:latest 2>/dev/null && echo "✓ Removed fazle-ai-fazle-api:latest" || echo "⚠ fazle-ai-fazle-api:latest not found"

echo ""
echo "--- Final dangling cleanup ---"
docker image prune -f

echo ""
DISK_AFTER=$(df -h / | tail -1 | awk '{print $3}')
echo "=== RESULTS ==="
echo "Disk BEFORE: $DISK_BEFORE"
echo "Disk AFTER:  $DISK_AFTER"
echo ""
docker system df
echo ""
df -h /
echo ""
echo "=== PHASE 1 COMPLETE ==="
