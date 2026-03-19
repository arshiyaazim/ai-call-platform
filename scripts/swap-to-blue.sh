#!/usr/bin/env bash
set -euo pipefail

echo "=== Swap nginx upstream to BLUE (port 8101) ==="
sudo bash -c 'echo "server 127.0.0.1:8101;" > /etc/nginx/upstreams/fazle-api.conf'
echo "Config written."

cat /etc/nginx/upstreams/fazle-api.conf
echo "---"

sudo nginx -t
sudo nginx -s reload
echo "Nginx reloaded."

echo "=== Stop GREEN container ==="
sleep 3
docker stop fazle-api-green
docker rm fazle-api-green
echo "GREEN removed."

echo "=== Update state file ==="
sudo bash -c 'echo blue > /var/lib/rolling-deploy/fazle-api.slot'

echo "=== Verify ==="
cat /var/lib/rolling-deploy/fazle-api.slot
docker ps --filter name=fazle-api --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

echo "=== SWAP COMPLETE ==="
