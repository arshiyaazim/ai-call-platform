#!/bin/bash
# Check network membership for key services
for c in ai-redis ollama prometheus ai-postgres; do
  echo "=== $c ==="
  docker inspect "$c" -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null
  echo ""
done

# Check Redis password
echo "=== Redis Password ==="
docker exec ai-redis printenv REDIS_PASSWORD 2>/dev/null || echo "No REDIS_PASSWORD env var"

# Check Redis auth 
echo "=== Redis Auth Test ==="  
docker exec ai-redis redis-cli PING 2>&1

# Check .env for redis password
echo "=== .env Redis ==="
grep -i REDIS /home/azim/ai-call-platform/.env 2>/dev/null | head -5

# Check fazle queue key
echo "=== Queue Keys ==="
docker exec ai-redis redis-cli KEYS '*queue*' 2>&1 | head -10
docker exec ai-redis redis-cli KEYS '*fazle*' 2>&1 | head -10
