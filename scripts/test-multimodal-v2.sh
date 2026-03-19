#!/usr/bin/env bash
set -euo pipefail

echo "=== DNS Test from fazle-api-blue ==="
docker exec fazle-api-blue python -c 'import socket; print("fazle-memory resolves to:", socket.gethostbyname("fazle-memory"))'

echo ""
echo "=== Direct call from fazle-api-blue to fazle-memory:8300/health ==="
docker exec fazle-api-blue python -c '
import urllib.request
try:
    resp = urllib.request.urlopen("http://fazle-memory:8300/health", timeout=5)
    print("HEALTH:", resp.read().decode())
except Exception as e:
    print("ERROR:", e)
'

echo ""
echo "=== Search-multimodal from fazle-api-blue ==="
docker exec fazle-api-blue python -c '
import urllib.request, json
data = json.dumps({"query": "test image", "user_id": "test_user", "limit": 3}).encode()
req = urllib.request.Request("http://fazle-memory:8300/search-multimodal", data=data, headers={"Content-Type": "application/json"})
try:
    resp = urllib.request.urlopen(req, timeout=10)
    print("RESULT:", resp.read().decode())
except Exception as e:
    print("ERROR:", e)
'

echo ""
echo "=== API proxy search-multimodal (via curl to 8101) ==="
curl -s -X POST http://127.0.0.1:8101/fazle/memory/search-multimodal \
  -H "Content-Type: application/json" \
  -d '{"query": "test image", "user_id": "test_user", "limit": 3}'
echo ""

echo ""
echo "=== Brain Health ==="
docker exec fazle-brain python -c '
import urllib.request
print(urllib.request.urlopen("http://localhost:8400/health").read().decode())
'

echo ""
echo "=== UI check ==="
curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" http://127.0.0.1:3020

echo ""
echo "=== TESTS DONE ==="
