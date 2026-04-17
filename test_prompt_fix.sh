#!/bin/bash
API_KEY="2aMFFfIaGDfgfP6JiXaevEgMRx9aZtgAzYriHGRcpvdEcWCtp7Xpqul0BYdjFchq"

echo "=== Test 1: Salary query ==="
START=$(date +%s%N)
RESP=$(curl -s -X POST http://localhost:8100/fazle/chat \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $API_KEY" \
  -d '{"message":"Samir er salary koto?","conversation_id":"test-pf-1","sender_phone":"+8801700000001"}')
END=$(date +%s%N)
MS=$(( (END - START) / 1000000 ))
echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Reply: {d.get(\"reply\",\"EMPTY\")[:200]}')" 2>/dev/null || echo "Raw: $RESP"
echo "Time: ${MS}ms"

echo ""
echo "=== Test 2: English greeting ==="
START=$(date +%s%N)
RESP=$(curl -s -X POST http://localhost:8100/fazle/chat \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $API_KEY" \
  -d '{"message":"Hello, how are you?","conversation_id":"test-pf-2","sender_phone":"+8801700000002"}')
END=$(date +%s%N)
MS=$(( (END - START) / 1000000 ))
echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Reply: {d.get(\"reply\",\"EMPTY\")[:200]}')" 2>/dev/null || echo "Raw: $RESP"
echo "Time: ${MS}ms"

echo ""
echo "=== Test 3: Duty query ==="
START=$(date +%s%N)
RESP=$(curl -s -X POST http://localhost:8100/fazle/chat \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $API_KEY" \
  -d '{"message":"Kal ke ke duty te ache?","conversation_id":"test-pf-3","sender_phone":"+8801700000001"}')
END=$(date +%s%N)
MS=$(( (END - START) / 1000000 ))
echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Reply: {d.get(\"reply\",\"EMPTY\")[:200]}')" 2>/dev/null || echo "Raw: $RESP"
echo "Time: ${MS}ms"

echo ""
echo "=== Test 4: Payment request ==="
START=$(date +%s%N)
RESP=$(curl -s -X POST http://localhost:8100/fazle/chat \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $API_KEY" \
  -d '{"message":"Karim ke 1000 taka dao","conversation_id":"test-pf-4","sender_phone":"+8801700000001"}')
END=$(date +%s%N)
MS=$(( (END - START) / 1000000 ))
echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Reply: {d.get(\"reply\",\"EMPTY\")[:200]}')" 2>/dev/null || echo "Raw: $RESP"
echo "Time: ${MS}ms"

echo ""
echo "=== Brain logs (last 15 lines) ==="
docker logs fazle-brain --tail 15 2>&1 | grep -E 'truncat|prompt|LLM|empty|gateway|route'
