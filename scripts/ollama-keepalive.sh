#!/bin/bash
# Periodic keepalive for Ollama qwen2.5:0.5b model
# Sends a minimal inference request every 5 minutes to prevent model unloading
# Run as: docker exec ollama /scripts/ollama-keepalive.sh
# Or via cron/systemd timer on the host

OLLAMA_URL="${OLLAMA_URL:-http://ollama:11434}"
MODEL="${VOICE_FAST_MODEL:-qwen2.5:0.5b}"
INTERVAL="${KEEPALIVE_INTERVAL:-300}"  # 5 minutes

echo "[keepalive] Starting Ollama keepalive for model=$MODEL interval=${INTERVAL}s"

while true; do
    # Minimal request — 1 token, keeps model loaded
    RESPONSE=$(curl -sf -o /dev/null -w "%{http_code}" \
        --max-time 30 \
        "$OLLAMA_URL/api/generate" \
        -d "{\"model\":\"$MODEL\",\"prompt\":\"hi\",\"stream\":false,\"options\":{\"num_predict\":1}}")
    
    if [ "$RESPONSE" = "200" ]; then
        echo "[keepalive] $(date '+%H:%M:%S') Model $MODEL pinged OK"
    else
        echo "[keepalive] $(date '+%H:%M:%S') WARN: ping failed (HTTP $RESPONSE)"
    fi
    
    sleep "$INTERVAL"
done
