#!/bin/bash
set -euo pipefail

echo "=== Test 1: API proxy search-multimodal ==="
curl -s -X POST http://127.0.0.1:8101/fazle/memory/search-multimodal \
  -H 'Content-Type: application/json' \
  -d '{"query": "test photo", "user_id": "test", "limit": 1}'

echo ""
echo ""
echo "=== Test 2: API direct health ==="
curl -s http://127.0.0.1:8101/health

echo ""
echo ""
echo "=== Test 3: Memory direct health ==="
docker exec fazle-memory python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8300/health').read().decode())"

echo ""
echo ""
echo "=== Test 4: Brain health ==="
docker exec fazle-brain python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8200/health').read().decode())"

echo ""
echo ""
echo "=== Test 5: LLM Gateway health ==="
docker exec fazle-llm-gateway python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8700/health').read().decode())" 2>/dev/null || echo "Gateway health endpoint unknown"

echo ""
echo ""
echo "=== Test 6: All fazle containers ==="
docker ps --format 'table {{.Names}}\t{{.Status}}' | grep fazle | sort

echo ""
echo "ALL TESTS COMPLETE"
