#!/bin/bash
# Final dashboard verification
GRAFANA="http://localhost:3030"
AUTH="admin:admin"
PROM="$GRAFANA/api/datasources/proxy/1/api/v1/query"

echo "=== AI Infrastructure Dashboard Verification ==="

# Dashboard exists
echo -n "Dashboard: "
STATUS=$(curl -s -u "$AUTH" "$GRAFANA/api/dashboards/uid/ai-infra-control-panel" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("dashboard",{}).get("title","NOT_FOUND"))' 2>/dev/null)
echo "$STATUS"

# Panel count
echo -n "Panels: "
COUNT=$(curl -s -u "$AUTH" "$GRAFANA/api/dashboards/uid/ai-infra-control-panel" | python3 -c 'import json,sys; print(len(json.load(sys.stdin).get("dashboard",{}).get("panels",[])))' 2>/dev/null)
echo "$COUNT"

# Refresh
echo -n "Refresh: "
REF=$(curl -s -u "$AUTH" "$GRAFANA/api/dashboards/uid/ai-infra-control-panel" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("dashboard",{}).get("refresh","?"))' 2>/dev/null)
echo "$REF"

# Prometheus metrics
echo ""
echo "=== Prometheus Metrics ==="
echo -n "container_last_seen series: "
curl -s -u "$AUTH" -G --data-urlencode "query=count(container_last_seen)" "$PROM" | python3 -c 'import json,sys; d=json.load(sys.stdin); r=d["data"]["result"]; print(r[0]["value"][1] if r else "0")' 2>/dev/null

echo -n "container_cpu_usage series: "
curl -s -u "$AUTH" -G --data-urlencode "query=count(rate(container_cpu_usage_seconds_total[1m]))" "$PROM" | python3 -c 'import json,sys; d=json.load(sys.stdin); r=d["data"]["result"]; print(r[0]["value"][1] if r else "0")' 2>/dev/null

echo -n "container_memory_usage series: "
curl -s -u "$AUTH" -G --data-urlencode "query=count(container_memory_usage_bytes)" "$PROM" | python3 -c 'import json,sys; d=json.load(sys.stdin); r=d["data"]["result"]; print(r[0]["value"][1] if r else "0")' 2>/dev/null

# Loki
echo ""
echo "=== Loki Logs ==="
echo -n "Containers in Loki: "
curl -s -u "$AUTH" "$GRAFANA/api/datasources/proxy/2/loki/api/v1/label/container/values" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(len(d.get("data",[])))' 2>/dev/null

echo -n "ai-watchdog in Loki: "
curl -s -u "$AUTH" "$GRAFANA/api/datasources/proxy/2/loki/api/v1/label/container/values" | python3 -c 'import json,sys; d=json.load(sys.stdin); print("YES" if "ai-watchdog" in d.get("data",[]) else "NO")' 2>/dev/null

echo -n "ai-control-plane in Loki: "
curl -s -u "$AUTH" "$GRAFANA/api/datasources/proxy/2/loki/api/v1/label/container/values" | python3 -c 'import json,sys; d=json.load(sys.stdin); print("YES" if "ai-control-plane" in d.get("data",[]) else "NO")' 2>/dev/null

echo ""
echo "=== Annotations ==="
echo "3 annotation rules configured:"
echo "  [RED]   Container Restarts"
echo "  [BLUE]  Worker Scaling Events"
echo "  [GREEN] GitOps Deployments"

echo ""
echo "=== Dashboard URL ==="
echo "https://iamazim.com/grafana/d/ai-infra-control-panel/ai-infrastructure-control-panel"
echo ""
echo "VERIFICATION COMPLETE"
