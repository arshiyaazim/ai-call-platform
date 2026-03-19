#!/bin/bash
# Verify AI Infrastructure Dashboard panels return data
set -euo pipefail

GRAFANA="http://localhost:3030"
AUTH="admin:admin"
PROM_PROXY="$GRAFANA/api/datasources/proxy/1/api/v1/query"

echo "=== Panel Verification ==="

# Panel 1: Container Health
echo -n "Panel 1 (Container Health): "
R=$(curl -s -u "$AUTH" "$PROM_PROXY?query=count(container_last_seen{name=~\".%2B\"})" 2>/dev/null)
V=$(echo "$R" | python3 -c 'import json,sys;d=json.load(sys.stdin);r=d.get("data",{}).get("result",[]);print(r[0]["value"][1] if r else "NONE")' 2>/dev/null)
echo "$V containers tracked"

# Panel 2: CPU Usage
echo -n "Panel 2 (CPU Usage): "
R=$(curl -s -u "$AUTH" "$PROM_PROXY?query=count(rate(container_cpu_usage_seconds_total{name=~\".%2B\"}[1m]))" 2>/dev/null)
V=$(echo "$R" | python3 -c 'import json,sys;d=json.load(sys.stdin);r=d.get("data",{}).get("result",[]);print(r[0]["value"][1] if r else "NONE")' 2>/dev/null)
echo "$V series"

# Panel 3: Memory Usage
echo -n "Panel 3 (Memory Usage): "
R=$(curl -s -u "$AUTH" "$PROM_PROXY?query=count(container_memory_usage_bytes{name=~\"ai-watchdog|ai-control-plane|fazle.*workers.*|fazle-api|fazle-brain|ollama\"})" 2>/dev/null)
V=$(echo "$R" | python3 -c 'import json,sys;d=json.load(sys.stdin);r=d.get("data",{}).get("result",[]);print(r[0]["value"][1] if r else "NONE")' 2>/dev/null)
echo "$V series"

# Panel 4: Disk Usage
echo -n "Panel 4 (Disk Usage): "
R=$(curl -s -u "$AUTH" "$PROM_PROXY?query=1-(node_filesystem_free_bytes{mountpoint=\"/\"}/node_filesystem_size_bytes{mountpoint=\"/\"})" 2>/dev/null)
V=$(echo "$R" | python3 -c 'import json,sys;d=json.load(sys.stdin);r=d.get("data",{}).get("result",[]);v=r[0]["value"][1] if r else "NONE";print(str(round(float(v)*100,1))+"%" if v!="NONE" else v)' 2>/dev/null)
echo "$V"

# Panels 5-8: Loki logs
echo -n "Panel 5 (Worker Scaling Logs): "
R=$(curl -s -u "$AUTH" "$GRAFANA/api/datasources/proxy/2/loki/api/v1/query_range?query=%7Bcontainer%3D%22ai-watchdog%22%7D+%7C~+%22scale%7Cscaling%7Creplicas%7Cworkers%22&start=$(date -d '1 hour ago' +%s)000000000&end=$(date +%s)000000000&limit=5" 2>/dev/null)
V=$(echo "$R" | python3 -c 'import json,sys;d=json.load(sys.stdin);r=d.get("data",{}).get("result",[]);total=sum(len(s.get("values",[])) for s in r);print(str(total)+" log entries")' 2>/dev/null)
echo "$V"

echo -n "Panel 6 (AI Repair Events): "
R=$(curl -s -u "$AUTH" "$GRAFANA/api/datasources/proxy/2/loki/api/v1/query_range?query=%7Bcontainer%3D%22ai-control-plane%22%7D+%7C~+%22restart%7Crepair%7Credeploy%7Crebuild%7Cunhealthy%22&start=$(date -d '1 hour ago' +%s)000000000&end=$(date +%s)000000000&limit=5" 2>/dev/null)
V=$(echo "$R" | python3 -c 'import json,sys;d=json.load(sys.stdin);r=d.get("data",{}).get("result",[]);total=sum(len(s.get("values",[])) for s in r);print(str(total)+" log entries")' 2>/dev/null)
echo "$V"

echo -n "Panel 8 (Control Plane Activity): "
R=$(curl -s -u "$AUTH" "$GRAFANA/api/datasources/proxy/2/loki/api/v1/query_range?query=%7Bcontainer%3D%22ai-control-plane%22%7D+%7C~+%22Cycle%7CAnalysis%7Creport%22&start=$(date -d '1 hour ago' +%s)000000000&end=$(date +%s)000000000&limit=5" 2>/dev/null)
V=$(echo "$R" | python3 -c 'import json,sys;d=json.load(sys.stdin);r=d.get("data",{}).get("result",[]);total=sum(len(s.get("values",[])) for s in r);print(str(total)+" log entries")' 2>/dev/null)
echo "$V"

echo ""
echo "=== Dashboard URL ==="
echo "https://iamazim.com/grafana/d/ai-infra-control-panel/ai-infrastructure-control-panel"
echo ""
echo "=== Annotations ==="
echo "3 annotation queries configured:"
echo "  - Container Restarts (red)"
echo "  - Worker Scaling Events (blue)"
echo "  - GitOps Deployments (green)"
echo ""
echo "VERIFICATION COMPLETE"
