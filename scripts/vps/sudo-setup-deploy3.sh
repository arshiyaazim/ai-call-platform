#!/bin/bash
set -euo pipefail

echo "============================================"
echo " VPS Sudo Setup — Deploy #3"
echo "============================================"

echo "[1/5] Installing jq..."
apt-get update -qq && apt-get install -y -qq jq 2>/dev/null || true
echo "  jq: $(jq --version 2>/dev/null || echo 'skipped')"

echo "[2/5] Creating nginx upstream directory..."
mkdir -p /etc/nginx/upstreams
cat > /etc/nginx/upstreams/fazle-api.conf << 'EOF'
# Managed by deploy-rolling.sh — do not edit manually
# Default: compose-managed instance on port 8100
server 127.0.0.1:8100 max_fails=3 fail_timeout=10s;
EOF
chown -R azim:azim /etc/nginx/upstreams
echo "  /etc/nginx/upstreams/fazle-api.conf created"
cat /etc/nginx/upstreams/fazle-api.conf

echo "[3/5] Creating rolling deploy state directory..."
mkdir -p /var/lib/rolling-deploy
chown azim:azim /var/lib/rolling-deploy
echo "  /var/lib/rolling-deploy/ created"

echo "[4/5] Updating fazle nginx config with upstream cluster..."
cp /etc/nginx/sites-available/fazle.iamazim.com.conf \
   /etc/nginx/sites-available/fazle.iamazim.com.conf.bak-pre-rolling
cp /home/azim/ai-call-platform/configs/nginx/fazle.iamazim.com.conf \
   /etc/nginx/sites-available/fazle.iamazim.com.conf
echo "  fazle.iamazim.com.conf updated (upstream cluster + connection draining)"

echo "[5/5] Testing and reloading nginx..."
nginx -t && systemctl reload nginx
echo "  nginx reloaded successfully"

echo ""
echo "ALL SUDO SETUP COMPLETE"
