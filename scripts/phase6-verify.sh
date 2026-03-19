#!/bin/bash
set -e
echo "=========================================="
echo "  PHASE 6: FULL SYSTEM VERIFICATION"
echo "=========================================="
echo ""

# 1. Container Health
echo "=== 1. Container Health ==="
total=$(docker ps -q | wc -l)
healthy=$(docker ps --filter health=healthy -q | wc -l)
unhealthy=$(docker ps --filter health=unhealthy -q | wc -l)
echo "Total containers: $total"
echo "Healthy: $healthy"
echo "Unhealthy: $unhealthy"
echo ""
docker ps --format 'table {{.Names}}\t{{.Status}}' | sort
echo ""

# 2. Compose Project Labels
echo "=== 2. Compose Project Labels ==="
for id in $(docker ps -q); do
  name=$(docker inspect --format '{{.Name}}' "$id" | sed 's/^\///')
  project=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$id")
  echo "$name -> $project"
done | sort
echo ""

# 3. Disk Usage
echo "=== 3. Disk Usage ==="
df -h / | tail -1
echo ""
docker system df
echo ""

# 4. HTTP Endpoint Tests
echo "=== 4. HTTP Endpoint Tests ==="
echo -n "fazle-api (8101): "
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8101/health 2>/dev/null || echo "FAIL"
echo ""
echo -n "fazle-ui (3000): "
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3000/ 2>/dev/null || echo "FAIL"
echo ""
echo -n "dograh-api (8200): "
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8200/health 2>/dev/null || echo "FAIL"
echo ""
echo -n "dograh-ui (3001): "
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3001/ 2>/dev/null || echo "FAIL"
echo ""
echo -n "grafana (3100): "
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3100/api/health 2>/dev/null || echo "FAIL"
echo ""
echo -n "prometheus (9090): "
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9090/-/ready 2>/dev/null || echo "FAIL"
echo ""
echo -n "minio (9000): "
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9000/minio/health/live 2>/dev/null || echo "FAIL"
echo ""
echo -n "qdrant (6333): "
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:6333/healthz 2>/dev/null || echo "FAIL"
echo ""
echo -n "loki (3200): "
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3200/ready 2>/dev/null || echo "FAIL"
echo ""

# 5. Database Connectivity
echo ""
echo "=== 5. Database Connectivity ==="
echo -n "PostgreSQL: "
docker exec ai-postgres pg_isready -U fazle 2>/dev/null && echo "OK" || echo "FAIL"
echo -n "Redis: "
docker exec ai-redis redis-cli ping 2>/dev/null || echo "FAIL"
echo ""

# 6. Volume Data Integrity
echo "=== 6. Volume Data Integrity ==="
echo -n "postgres_data size: "
docker exec ai-postgres du -sh /var/lib/postgresql/data 2>/dev/null | cut -f1
echo -n "redis_data size: "
docker exec ai-redis du -sh /data 2>/dev/null | cut -f1
echo -n "minio_data size: "
docker exec minio du -sh /data 2>/dev/null | cut -f1
echo -n "qdrant_data size: "
docker exec qdrant du -sh /qdrant/storage 2>/dev/null | cut -f1
echo ""

# 7. Error Log Check (last 5 min)
echo "=== 7. Recent Error Logs (last 5 min) ==="
for c in fazle-api fazle-voice dograh-api; do
  errors=$(docker logs --since 5m "$c" 2>&1 | grep -ci "error\|traceback\|exception" || true)
  echo "$c: $errors error(s)"
done
echo ""

# 8. Network Connectivity Between Services
echo "=== 8. Inter-service Network ==="
echo -n "fazle-api -> ai-postgres: "
docker exec fazle-api python3 -c "import socket; socket.create_connection(('ai-postgres', 5432), 3); print('OK')" 2>/dev/null || echo "FAIL"
echo -n "fazle-api -> ai-redis: "
docker exec fazle-api python3 -c "import socket; socket.create_connection(('ai-redis', 6379), 3); print('OK')" 2>/dev/null || echo "FAIL"
echo -n "fazle-api -> fazle-memory: "
docker exec fazle-api python3 -c "import socket; socket.create_connection(('fazle-memory', 8300), 3); print('OK')" 2>/dev/null || echo "FAIL"
echo ""

# 9. Orphaned Resources
echo "=== 9. Orphaned Resources ==="
echo -n "Dangling volumes: "
docker volume ls -qf dangling=true | wc -l
echo -n "Dangling images: "
docker images -qf dangling=true | wc -l
echo ""

echo "=========================================="
echo "  VERIFICATION COMPLETE"
echo "=========================================="
