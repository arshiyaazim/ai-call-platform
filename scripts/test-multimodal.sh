#!/usr/bin/env bash
set -euo pipefail

echo "=== Memory Service Health ==="
docker exec fazle-memory python -c 'import urllib.request; print(urllib.request.urlopen("http://localhost:8300/health").read().decode())'

echo ""
echo "=== Memory Search-Multimodal Endpoint ==="
docker exec fazle-api-blue python -c '
import urllib.request, json
data = json.dumps({"query": "test image", "user_id": "test_user", "limit": 3}).encode()
req = urllib.request.Request("http://fazle-memory:8300/search-multimodal", data=data, headers={"Content-Type": "application/json"})
resp = urllib.request.urlopen(req)
print(resp.read().decode())
'

echo ""
echo "=== API Search-Multimodal Proxy ==="
curl -s -X POST http://127.0.0.1:8101/fazle/memory/search-multimodal \
  -H "Content-Type: application/json" \
  -d '{"query": "test image", "user_id": "test_user", "limit": 3}'

echo ""
echo "=== Brain Health ==="
docker exec fazle-brain python -c 'import urllib.request; print(urllib.request.urlopen("http://localhost:8400/health").read().decode())'

echo ""
echo "=== UI Health (port 3020) ==="
curl -s http://127.0.0.1:3020 | head -c 200
echo ""

echo ""
echo "=== ENDPOINT TESTS COMPLETE ==="
