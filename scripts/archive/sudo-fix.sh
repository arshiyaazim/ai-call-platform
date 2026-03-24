#!/usr/bin/env bash
# ============================================================
# sudo-fix.sh — Fixes remaining root-level issues
# Run: sudo bash ~/ai-call-platform/scripts/sudo-fix.sh
# ============================================================
set -euo pipefail

PROJECT_DIR="/home/azim/ai-call-platform"

echo "============================================"
echo " Root Fix — AI Voice Agent Platform"
echo "============================================"

# ── Step 1: Re-install updated Nginx configs ────────────────
echo "[1/4] Installing updated Nginx configs..."
cp "$PROJECT_DIR/configs/nginx/iamazim.com.conf" /etc/nginx/sites-available/iamazim.com.conf
cp "$PROJECT_DIR/configs/nginx/api.iamazim.com.conf" /etc/nginx/sites-available/api.iamazim.com.conf
cp "$PROJECT_DIR/configs/nginx/livekit.iamazim.com.conf" /etc/nginx/sites-available/livekit.iamazim.com.conf
echo "  Done"

# ── Step 2: Test and reload Nginx ───────────────────────────
echo "[2/4] Testing Nginx..."
nginx -t
systemctl reload nginx
echo "  Nginx reloaded"

# ── Step 3: Expand SSL cert (webroot method) ────────────────
echo "[3/4] Expanding SSL certificate..."
# Create webroot dir if missing
mkdir -p /var/www/certbot

# Kill any stale certbot processes
pkill -f certbot 2>/dev/null || true
sleep 2

# Remove any certbot lock files
rm -f /var/lib/letsencrypt/.certbot.lock 2>/dev/null || true

certbot certonly --webroot -w /var/www/certbot \
    --cert-name iamazim.com \
    -d iamazim.com \
    -d www.iamazim.com \
    -d api.iamazim.com \
    -d voice.iamazim.com \
    -d livekit.iamazim.com \
    -d turn.iamazim.com \
    --agree-tos \
    --no-eff-email \
    --keep-until-expiring \
    --expand

echo "  SSL cert updated. New domains:"
openssl x509 -in /etc/letsencrypt/live/iamazim.com/cert.pem -noout -text 2>/dev/null | grep DNS || true

# ── Step 4: Firewall ────────────────────────────────────────
echo "[4/4] Configuring firewall..."
if command -v ufw &> /dev/null; then
    ufw allow 22/tcp 2>/dev/null || true
    ufw allow 80/tcp 2>/dev/null || true
    ufw allow 443/tcp 2>/dev/null || true
    ufw allow 7881/tcp 2>/dev/null || true
    ufw allow 50000:50200/udp 2>/dev/null || true
    ufw allow 3478 2>/dev/null || true
    ufw allow 5349 2>/dev/null || true
    ufw allow 49152:49252/udp 2>/dev/null || true
    echo "y" | ufw enable 2>/dev/null || true
    ufw status numbered
    echo "  Firewall configured"
else
    echo "  UFW not installed — skipping"
fi

echo ""
echo "============================================"
echo " All fixes applied!"
echo " Next: cd ~/ai-call-platform && docker compose up -d"
echo "============================================"
