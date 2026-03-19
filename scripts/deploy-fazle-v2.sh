#!/usr/bin/env bash
# ============================================================
# deploy-fazle-v2.sh — Deploy Fazle AI v2 (Jarvis upgrade)
# Usage: bash scripts/deploy-fazle-v2.sh
# Run from LOCAL machine with SSH access to VPS
# ============================================================
set -euo pipefail

VPS_IP="5.189.131.48"
VPS_USER="azim"
VPS_DIR="/home/azim/ai-call-platform"

echo "============================================"
echo " Fazle AI v2 Deployment — Jarvis Upgrade"
echo " Target: ${VPS_USER}@${VPS_IP}"
echo "============================================"
echo ""

# ── Pre-flight ──────────────────────────────────────────────
echo "── Pre-flight checks ──"
if ! ssh -o ConnectTimeout=10 "${VPS_USER}@${VPS_IP}" "echo OK" >/dev/null 2>&1; then
    echo "✗ Cannot reach VPS via SSH"
    exit 1
fi
echo "  ✓ SSH connectivity OK"

# Check git status
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    echo "  ⚠ Uncommitted changes detected"
    echo "  Commit and push before deploying."
    exit 1
fi
echo "  ✓ Working directory clean"
echo ""

# ── Step 1: Push code ──────────────────────────────────────
echo "[1/7] Pushing code to remote..."
git push origin "$(git branch --show-current)" 2>&1 || {
    echo "  ⚠ git push failed — ensure remote is configured"
    exit 1
}
echo "  ✓ Code pushed"
echo ""

# ── Step 2: Pull on VPS ───────────────────────────────────
echo "[2/7] Pulling latest code on VPS..."
ssh "${VPS_USER}@${VPS_IP}" << 'REMOTE'
  set -e
  cd ~/ai-call-platform
  git stash 2>/dev/null || true
  git pull --rebase origin main 2>/dev/null || git pull origin main
  echo "  ✓ Code pulled"
REMOTE
echo ""

# ── Step 3: Run DB migrations for task engine ──────────────
echo "[3/7] Running database migrations..."
ssh "${VPS_USER}@${VPS_IP}" << 'REMOTE'
  set -e
  cd ~/ai-call-platform

  # The task engine auto-creates tables on startup via ensure_tables()
  # but we need to ensure the event_triggers table and new columns exist
  # This happens automatically when the service starts
  echo "  ✓ Migrations will run on service startup (ensure_tables)"
REMOTE
echo ""

# ── Step 4: Validate compose config ───────────────────────
echo "[4/7] Validating docker-compose configuration..."
ssh "${VPS_USER}@${VPS_IP}" << 'REMOTE'
  set -e
  cd ~/ai-call-platform

  # Validate all 3 stacks
  cd ai-infra && docker compose config -q && echo "  ✓ ai-infra compose valid"
  cd ../dograh && docker compose config -q && echo "  ✓ dograh compose valid"
  cd ../fazle-ai && docker compose config -q && echo "  ✓ fazle-ai compose valid"
REMOTE
echo ""

# ── Step 5: Rebuild Fazle services ─────────────────────────
echo "[5/7] Rebuilding Fazle AI services..."
echo "  Services: brain, memory, task-engine, voice, web-intelligence, api"
ssh "${VPS_USER}@${VPS_IP}" << 'REMOTE'
  set -e
  cd ~/ai-call-platform/fazle-ai

  docker compose build --no-cache \
    fazle-brain \
    fazle-memory \
    fazle-task-engine \
    fazle-voice \
    fazle-web-intelligence \
    fazle-api

  echo "  ✓ Build complete"
REMOTE
echo ""

# ── Step 6: Rolling restart ───────────────────────────────
echo "[6/7] Rolling restart of Fazle services..."
ssh "${VPS_USER}@${VPS_IP}" << 'REMOTE'
  set -e
  cd ~/ai-call-platform/fazle-ai

  # Restart services in dependency order
  echo "  Restarting fazle-memory..."
  docker compose up -d fazle-memory
  sleep 5

  echo "  Restarting fazle-task-engine..."
  docker compose up -d fazle-task-engine
  sleep 3

  echo "  Restarting fazle-web-intelligence..."
  docker compose up -d fazle-web-intelligence
  sleep 3

  echo "  Restarting fazle-brain..."
  docker compose up -d fazle-brain
  sleep 5

  echo "  Restarting fazle-voice..."
  docker compose up -d fazle-voice
  sleep 3

  echo "  Restarting fazle-api..."
  docker compose up -d fazle-api
  sleep 3

  echo "  Starting any remaining services..."
  docker compose up -d --remove-orphans

  echo "  ✓ All services restarted"
REMOTE
echo ""

# ── Step 7: Health verification ────────────────────────────
echo "[7/7] Verifying service health..."
sleep 10
ssh "${VPS_USER}@${VPS_IP}" << 'REMOTE'
  set -e
  cd ~/ai-call-platform

  PASS=0
  FAIL=0

  check_health() {
    local name="$1"
    local url="$2"
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null || echo "000")
    if [ "$STATUS" = "200" ]; then
      echo "  ✓ $name — healthy"
      PASS=$((PASS + 1))
    else
      echo "  ✗ $name — HTTP $STATUS"
      FAIL=$((FAIL + 1))
    fi
  }

  echo ""
  echo "── Service Health ──"
  check_health "Brain v2"        "http://localhost:8200/health"
  check_health "Brain Status"    "http://localhost:8200/status"
  check_health "Memory"          "http://localhost:8300/health"
  check_health "Task Engine v2"  "http://localhost:8400/health"
  check_health "Web Intel"       "http://localhost:8500/health"
  check_health "Voice"           "http://localhost:8700/health"
  check_health "API Gateway"     "http://localhost:8100/health"
  check_health "LLM Gateway"    "http://localhost:8800/health"

  echo ""
  echo "── New v2 Endpoints ──"
  # Test route endpoint
  ROUTE=$(curl -s --max-time 5 -X POST http://localhost:8200/route \
    -H "Content-Type: application/json" \
    -d '{"message":"hello"}' 2>/dev/null || echo "FAIL")
  if echo "$ROUTE" | grep -q "route"; then
    echo "  ✓ /route — working"
    PASS=$((PASS + 1))
  else
    echo "  ✗ /route — failed"
    FAIL=$((FAIL + 1))
  fi

  # Test agent chat
  AGENT=$(curl -s --max-time 15 -X POST http://localhost:8200/chat/agent \
    -H "Content-Type: application/json" \
    -d '{"message":"hi","user":"test"}' 2>/dev/null || echo "FAIL")
  if echo "$AGENT" | grep -q "reply\|response\|content"; then
    echo "  ✓ /chat/agent — working"
    PASS=$((PASS + 1))
  else
    echo "  ✗ /chat/agent — failed"
    FAIL=$((FAIL + 1))
  fi

  # Test triggers endpoint
  TRIGGERS=$(curl -s --max-time 5 http://localhost:8400/triggers 2>/dev/null || echo "FAIL")
  if echo "$TRIGGERS" | grep -q "triggers"; then
    echo "  ✓ /triggers — working"
    PASS=$((PASS + 1))
  else
    echo "  ✗ /triggers — failed"
    FAIL=$((FAIL + 1))
  fi

  # Test plugins endpoint
  PLUGINS=$(curl -s --max-time 5 http://localhost:8500/plugins 2>/dev/null || echo "FAIL")
  if echo "$PLUGINS" | grep -q "plugins\|tools"; then
    echo "  ✓ /plugins — working"
    PASS=$((PASS + 1))
  else
    echo "  ✗ /plugins — failed"
    FAIL=$((FAIL + 1))
  fi

  echo ""
  echo "── TTFB Latency Check ──"
  TTFB=$(curl -s -o /dev/null -w "%{time_starttransfer}" --max-time 10 \
    -X POST http://localhost:8200/chat/agent/stream \
    -H "Content-Type: application/json" \
    -d '{"message":"hello","user":"test"}' 2>/dev/null || echo "999")
  TTFB_MS=$(echo "$TTFB * 1000" | bc 2>/dev/null || echo "?")
  echo "  TTFB: ${TTFB_MS}ms (target: <500ms)"

  echo ""
  echo "============================================"
  echo " Results: $PASS passed, $FAIL failed"
  if [ "$FAIL" -eq 0 ]; then
    echo " ✓ Fazle AI v2 deployment SUCCESSFUL"
  else
    echo " ⚠ Some checks failed — review logs"
    echo "   docker compose -f fazle-ai/docker-compose.yaml logs --tail 50"
  fi
  echo "============================================"
REMOTE

echo ""
echo "============================================"
echo " Fazle AI v2 — Jarvis Upgrade Complete"
echo ""
echo " Access Points:"
echo "   Fazle UI:  https://fazle.iamazim.com"
echo "   Fazle API: https://fazle.iamazim.com/api/fazle/health"
echo "   Brain:     http://VPS:8200/status"
echo ""
echo " Quick test:"
echo '   curl -X POST http://VPS:8200/chat/agent -H "Content-Type: application/json" -d '"'"'{"message":"hello","user":"test"}'"'"
echo "============================================"
