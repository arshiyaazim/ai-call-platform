#!/usr/bin/env bash
# ============================================================
# create-networks.sh — Create shared external Docker networks
# Run ONCE before starting any stack.
# ============================================================
set -euo pipefail

NETWORKS=(
  "app-network"
  "db-network"
  "ai-network"
  "monitoring-network"
)

for net in "${NETWORKS[@]}"; do
  if docker network inspect "$net" >/dev/null 2>&1; then
    echo "[OK]  Network '$net' already exists"
  else
    docker network create "$net"
    echo "[NEW] Created network '$net'"
  fi
done

echo ""
echo "All networks ready. You can now start stacks with stack-up.sh"
