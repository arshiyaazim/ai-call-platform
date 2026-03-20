#!/usr/bin/env bash
# ============================================================
# health-check.sh — Comprehensive health check for all services
# Usage: bash scripts/health-check.sh
# ============================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

pass() { PASS=$((PASS+1)); printf "  ${GREEN}✓${NC} %s\n" "$1"; }
fail() { FAIL=$((FAIL+1)); printf "  ${RED}✗${NC} %s\n" "$1"; }
warn() { WARN=$((WARN+1)); printf "  ${YELLOW}⚠${NC} %s\n" "$1"; }

echo "============================================"
echo " Platform Health Check"
echo " $(date)"
echo "============================================"
echo ""

# ── Docker Daemon ───────────────────────────────────────────
echo -e "${CYAN}── Docker Daemon ──${NC}"
if docker info >/dev/null 2>&1; then
    pass "Docker daemon running"
else
    fail "Docker daemon not reachable"
    echo "  Cannot proceed without Docker."
    exit 1
fi
echo ""

# ── Docker Containers ──────────────────────────────────────
echo -e "${CYAN}── Docker Containers ──${NC}"
CONTAINERS=(
    "ai-postgres" "ai-redis" "minio"
    "dograh-api" "dograh-ui" "livekit" "coturn"
    "qdrant" "ollama"
    "fazle-api" "fazle-brain" "fazle-memory"
    "fazle-task-engine" "fazle-web-intelligence" "fazle-trainer" "fazle-ui"
    "fazle-guardrail-engine"
    "prometheus" "grafana" "loki" "promtail" "node-exporter" "cadvisor"
    "cloudflared-tunnel"
)
for c in "${CONTAINERS[@]}"; do
    STATUS=$(docker inspect --format='{{.State.Status}}' "$c" 2>/dev/null | tr -d '[:space:]' || echo "not-found")
    HEALTH=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$c" 2>/dev/null | tr -d '[:space:]' || echo "none")

    if [ "$STATUS" = "running" ] && { [ "$HEALTH" = "healthy" ] || [ "$HEALTH" = "none" ]; }; then
        pass "$(printf '%-25s running (%s)' "$c" "$HEALTH")"
    elif [ "$STATUS" = "not-found" ]; then
        warn "$(printf '%-25s not found' "$c")"
    else
        fail "$(printf '%-25s %s (%s)' "$c" "$STATUS" "$HEALTH")"
    fi
done
echo ""

# ── HTTP Endpoints ──────────────────────────────────────────
echo -e "${CYAN}── HTTP Endpoints ──${NC}"
check_endpoint() {
    local name=$1 url=$2 code
    code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time 10 "$url" 2>/dev/null || echo "000")
    if [ "$code" -ge 200 ] && [ "$code" -lt 400 ]; then
        pass "$(printf '%-30s HTTP %s' "$name" "$code")"
    else
        fail "$(printf '%-30s HTTP %s' "$name" "$code")"
    fi
}

check_endpoint "API Health"      "https://api.iamazim.com/api/v1/health"
check_endpoint "Dashboard"       "https://iamazim.com"
check_endpoint "Fazle UI (ext)"  "https://fazle.iamazim.com" 2>/dev/null || true
check_endpoint "LiveKit"         "http://127.0.0.1:7880"
check_endpoint "Fazle API"       "http://127.0.0.1:8100/health"
check_endpoint "Fazle UI"        "http://127.0.0.1:3020"
check_endpoint "Grafana"         "http://127.0.0.1:3030/api/health"
check_endpoint "Guardrail Engine" "http://127.0.0.1:9600/health"

# Internal-only services (no host port binding) — check via docker exec
PROM_OK=$(docker exec prometheus wget -q --spider http://localhost:9090/-/healthy 2>/dev/null && echo "OK" || echo "FAIL")
if [ "$PROM_OK" = "OK" ]; then
    pass "$(printf '%-30s healthy (docker exec)' 'Prometheus')"
else
    fail "$(printf '%-30s unreachable' 'Prometheus')"
fi
QDRANT_OK=$(docker exec qdrant bash -c 'echo > /dev/tcp/localhost/6333 && echo OK' 2>/dev/null || echo "FAIL")
if [ "$QDRANT_OK" = "OK" ]; then
    pass "$(printf '%-30s via docker exec' 'Qdrant')"
else
    fail "$(printf '%-30s unreachable' 'Qdrant')"
fi
LOKI_STATUS=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' loki 2>/dev/null | tr -d '[:space:]' || echo "unknown")
if [ "$LOKI_STATUS" = "healthy" ]; then
    pass "$(printf '%-30s healthy' 'Loki')"
else
    warn "$(printf '%-30s %s' 'Loki' "$LOKI_STATUS")"
fi
echo ""

# ── Ollama Model ────────────────────────────────────────────
echo -e "${CYAN}── Ollama Models ──${NC}"
MODELS=$(docker exec ollama ollama list 2>/dev/null || echo "")
if [ -n "$MODELS" ]; then
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        pass "$line"
    done <<< "$MODELS"
else
    warn "No models loaded or Ollama unreachable"
fi
echo ""

# ── Qdrant Collections ─────────────────────────────────────
echo -e "${CYAN}── Qdrant Collections ──${NC}"
# Qdrant has no curl/wget; query via python from fazle-memory which connects to it
COLLECTIONS=$(docker exec fazle-memory python -c "
import urllib.request, json
try:
    r = urllib.request.urlopen('http://qdrant:6333/collections', timeout=5)
    data = json.loads(r.read())
    for c in data.get('result', {}).get('collections', []):
        print(c['name'])
except: pass
" 2>/dev/null || echo "")
if [ -n "$COLLECTIONS" ]; then
    while IFS= read -r name; do
        [ -z "$name" ] && continue
        pass "Collection: $name"
    done <<< "$COLLECTIONS"
else
    warn "No Qdrant collections found"
fi
echo ""

# ── System Resources ───────────────────────────────────────
echo -e "${CYAN}── System Resources ──${NC}"
DISK_PCT=$(df / | awk 'NR==2 {gsub(/%/,""); print $5}')
MEM_PCT=$(free | awk 'NR==2 {printf "%.0f", $3/$2*100}')
LOAD=$(cat /proc/loadavg 2>/dev/null | awk '{print $1, $2, $3}' || echo "n/a")
CPUS=$(nproc 2>/dev/null || echo 1)

if [ "$DISK_PCT" -lt 80 ]; then
    pass "Disk: ${DISK_PCT}% used"
elif [ "$DISK_PCT" -lt 90 ]; then
    warn "Disk: ${DISK_PCT}% used (getting full)"
else
    fail "Disk: ${DISK_PCT}% used (CRITICAL)"
fi

if [ "$MEM_PCT" -lt 85 ]; then
    pass "Memory: ${MEM_PCT}% used"
elif [ "$MEM_PCT" -lt 95 ]; then
    warn "Memory: ${MEM_PCT}% used (high)"
else
    fail "Memory: ${MEM_PCT}% used (CRITICAL)"
fi

echo "  Load: $LOAD (${CPUS} CPUs)"

DOCKER_DISK=$(docker system df --format '{{.Type}}\t{{.Size}}\t{{.Reclaimable}}' 2>/dev/null || echo "")
if [ -n "$DOCKER_DISK" ]; then
    echo "  Docker disk:"
    while IFS= read -r line; do
        echo "    $line"
    done <<< "$DOCKER_DISK"
fi
echo ""

# ── Critical Ports ──────────────────────────────────────────
echo -e "${CYAN}── Critical Ports ──${NC}"
declare -A PORT_LABELS=(
    [80]="HTTP/Nginx" [443]="HTTPS/Nginx" [8000]="Dograh API"
    [3010]="Dograh UI" [7880]="LiveKit HTTP" [7881]="LiveKit RTC"
    [3478]="TURN/STUN" [5349]="TURN TLS" [8100]="Fazle API"
    [3020]="Fazle UI" [3030]="Grafana"
)
for port in 80 443 8000 3010 7880 7881 3478 5349 8100 3020 3030; do
    label="${PORT_LABELS[$port]:-unknown}"
    if ss -tlnp 2>/dev/null | grep -q ":$port " || ss -ulnp 2>/dev/null | grep -q ":$port "; then
        pass "$(printf 'Port %-6s %-15s listening' "$port" "($label)")"
    else
        warn "$(printf 'Port %-6s %-15s not listening' "$port" "($label)")"
    fi
done
echo ""

# ── Nginx ───────────────────────────────────────────────────
echo -e "${CYAN}── Nginx ──${NC}"
if systemctl is-active --quiet nginx 2>/dev/null; then
    pass "Nginx service active"
else
    fail "Nginx service not running"
fi
if sudo nginx -t 2>/dev/null; then
    pass "Nginx config valid"
else
    warn "Nginx config check (needs sudo)"
fi
echo ""

# ── SSL Certificates ───────────────────────────────────────
echo -e "${CYAN}── SSL Certificates ──${NC}"
for domain in iamazim.com api.iamazim.com livekit.iamazim.com fazle.iamazim.com; do
    EXPIRY=$(echo | timeout 5 openssl s_client -servername "$domain" -connect "$domain:443" 2>/dev/null | \
        openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2 || echo "")
    if [ -n "$EXPIRY" ]; then
        DAYS_LEFT=$(( ( $(date -d "$EXPIRY" +%s 2>/dev/null || echo 0) - $(date +%s) ) / 86400 )) || DAYS_LEFT=0
        if [ "$DAYS_LEFT" -gt 14 ]; then
            pass "$domain — expires in ${DAYS_LEFT} days"
        elif [ "$DAYS_LEFT" -gt 0 ]; then
            warn "$domain — expires in ${DAYS_LEFT} days (renew soon!)"
        else
            fail "$domain — EXPIRED or date parse error"
        fi
    else
        warn "$domain — could not check certificate"
    fi
done
echo ""

# ── Summary ─────────────────────────────────────────────────
echo "============================================"
echo -e " ${GREEN}✓ $PASS passed${NC}  ${RED}✗ $FAIL failed${NC}  ${YELLOW}⚠ $WARN warnings${NC}"
if [ $FAIL -eq 0 ]; then
    echo -e " ${GREEN}All critical checks passed${NC}"
else
    echo -e " ${RED}$FAIL check(s) failed — investigate above${NC}"
fi
echo "============================================"

exit $FAIL
