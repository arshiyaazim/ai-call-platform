#!/usr/bin/env bash
# ============================================================
# sudo-setup.sh — Run this manually with: sudo bash ~/ai-call-platform/scripts/sudo-setup.sh
# This script does all operations that require root privileges:
#   1. Install Nginx configs
#   2. Expand SSL cert to cover new subdomains
#   3. Configure firewall
# ============================================================
set -euo pipefail

PROJECT_DIR="/home/azim/ai-call-platform"

echo "============================================"
echo " Root Setup — AI Voice Agent Platform"
echo "============================================"
echo ""

# ── Step 1: Backup existing Nginx config ────────────────────
echo "[1/5] Backing up existing Nginx config..."
if [ -f /etc/nginx/sites-available/iamazim.com ]; then
    cp /etc/nginx/sites-available/iamazim.com /etc/nginx/sites-available/iamazim.com.bak.$(date +%Y%m%d)
    echo "  Backed up old config"
fi

# ── Step 2: Install new Nginx configs ───────────────────────
echo "[2/5] Installing Nginx site configs..."

cp "$PROJECT_DIR/configs/nginx/iamazim.com.conf" /etc/nginx/sites-available/iamazim.com.conf
cp "$PROJECT_DIR/configs/nginx/api.iamazim.com.conf" /etc/nginx/sites-available/api.iamazim.com.conf
cp "$PROJECT_DIR/configs/nginx/livekit.iamazim.com.conf" /etc/nginx/sites-available/livekit.iamazim.com.conf

# Remove old site link (old name without .conf)
rm -f /etc/nginx/sites-enabled/iamazim.com

# Enable new sites
ln -sf /etc/nginx/sites-available/iamazim.com.conf /etc/nginx/sites-enabled/iamazim.com.conf
ln -sf /etc/nginx/sites-available/api.iamazim.com.conf /etc/nginx/sites-enabled/api.iamazim.com.conf
ln -sf /etc/nginx/sites-available/livekit.iamazim.com.conf /etc/nginx/sites-enabled/livekit.iamazim.com.conf

echo "  Installed 3 Nginx configs"

# ── Step 3: Test Nginx ──────────────────────────────────────
echo "[3/5] Testing Nginx configuration..."
nginx -t
echo "  Nginx config is valid"

# Reload Nginx
systemctl reload nginx
echo "  Nginx reloaded"

# ── Step 4: Expand SSL certificate ──────────────────────────
echo "[4/5] Expanding SSL certificate to cover new subdomains..."
echo "  Current cert domains:"
openssl x509 -in /etc/letsencrypt/live/iamazim.com/cert.pem -noout -ext subjectAltName 2>/dev/null | tail -1 || true

certbot certonly --nginx \
    --expand \
    -d iamazim.com \
    -d www.iamazim.com \
    -d api.iamazim.com \
    -d voice.iamazim.com \
    -d livekit.iamazim.com \
    -d turn.iamazim.com \
    --non-interactive \
    --agree-tos \
    || echo "  ⚠ Certbot failed — you may need to run manually"

echo "  Updated cert domains:"
openssl x509 -in /etc/letsencrypt/live/iamazim.com/cert.pem -noout -ext subjectAltName 2>/dev/null | tail -1 || true

# ── Step 5: Firewall ────────────────────────────────────────
echo "[5/5] Configuring firewall..."

if command -v ufw &> /dev/null; then
    ufw allow 22/tcp comment "SSH" 2>/dev/null || true
    ufw allow 80/tcp comment "HTTP" 2>/dev/null || true
    ufw allow 443/tcp comment "HTTPS" 2>/dev/null || true
    ufw allow 7881/tcp comment "LiveKit RTC TCP" 2>/dev/null || true
    ufw allow 50000:50200/udp comment "LiveKit WebRTC UDP" 2>/dev/null || true
    ufw allow 3478/tcp comment "TURN STUN" 2>/dev/null || true
    ufw allow 3478/udp comment "TURN STUN UDP" 2>/dev/null || true
    ufw allow 5349/tcp comment "TURN TLS" 2>/dev/null || true
    ufw allow 5349/udp comment "TURN TLS UDP" 2>/dev/null || true
    ufw allow 49152:49252/udp comment "TURN relay UDP" 2>/dev/null || true
    echo "y" | ufw enable 2>/dev/null || true
    echo "  Firewall rules configured"
    ufw status | head -20
else
    echo "  UFW not installed, skipping firewall"
fi

# ── Step 6: Setup certbot auto-renewal ──────────────────────
if ! crontab -l 2>/dev/null | grep -q "certbot renew"; then
    (crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet --deploy-hook 'systemctl reload nginx'") | crontab -
    echo "  Added certbot auto-renewal cron"
fi

echo ""
echo "============================================"
echo " Root setup complete!"
echo " Now run: cd ~/ai-call-platform && bash scripts/deploy.sh"
echo "============================================"
