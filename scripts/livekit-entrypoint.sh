#!/bin/sh
set -e

# Expand environment variables in the LiveKit config template
sed \
  -e "s|\${REDIS_PASSWORD}|${REDIS_PASSWORD}|g" \
  -e "s|\${LIVEKIT_API_KEY}|${LIVEKIT_API_KEY}|g" \
  -e "s|\${LIVEKIT_API_SECRET}|${LIVEKIT_API_SECRET}|g" \
  -e "s|\${LIVEKIT_WEBHOOK_URL}|${LIVEKIT_WEBHOOK_URL}|g" \
  -e "s|\${AI_AGENT_WEBHOOK_URL}|${AI_AGENT_WEBHOOK_URL}|g" \
  /etc/livekit-template.yaml > /tmp/livekit.yaml

exec /livekit-server --config /tmp/livekit.yaml --node-ip "${VPS_IP:-5.189.131.48}"
