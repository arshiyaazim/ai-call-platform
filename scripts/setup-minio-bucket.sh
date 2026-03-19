#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="/home/azim/ai-call-platform/.env"
AK=$(grep '^MINIO_ACCESS_KEY=' "$ENV_FILE" | head -1 | cut -d= -f2)
SK=$(grep '^MINIO_SECRET_KEY=' "$ENV_FILE" | head -1 | cut -d= -f2)

echo "Setting up MinIO alias..."
docker exec minio mc alias set local http://localhost:9000 "$AK" "$SK"

echo "Creating bucket fazle-multimodal..."
docker exec minio mc mb --ignore-existing local/fazle-multimodal

echo "Adding 90-day lifecycle rule..."
docker exec minio mc ilm rule add local/fazle-multimodal --expiry-days 90 || echo "ILM rule may already exist or not supported, continuing..."

echo "Verifying bucket..."
docker exec minio mc ls local/ | grep fazle-multimodal

echo "MINIO_SETUP_COMPLETE"
