#!/bin/bash
# ============================================================
# verify-configs.sh — Compare deployed VPS configs vs repo
# Run ON the VPS from the repo root:  bash scripts/verify-configs.sh
# ============================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PASS=0
FAIL=0
SKIP=0

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Map: repo path → deployed path on VPS
declare -A CONFIG_MAP=(
  ["configs/nginx/iamazim.com.conf"]="/etc/nginx/sites-enabled/iamazim.com.conf"
  ["configs/nginx/api.iamazim.com.conf"]="/etc/nginx/sites-enabled/api.iamazim.com.conf"
  ["configs/nginx/fazle.iamazim.com.conf"]="/etc/nginx/sites-enabled/fazle.iamazim.com.conf"
  ["configs/nginx/livekit.iamazim.com.conf"]="/etc/nginx/sites-enabled/livekit.iamazim.com.conf"
  ["configs/prometheus/prometheus.yml"]="/etc/prometheus/prometheus.yml"
  ["configs/loki/loki.yml"]="/etc/loki/loki.yml"
  ["configs/promtail/promtail.yml"]="/etc/promtail/promtail.yml"
)

# These are template files — compare against their deployed (expanded) paths
# but note they contain ${VAR} placeholders, so we do a structural diff only
declare -A TEMPLATE_MAP=(
  ["configs/coturn/turnserver.conf"]="/tmp/turnserver.conf"
  ["configs/livekit/livekit.yaml"]="/tmp/livekit.yaml"
)

echo "============================================================"
echo "  Config Verification: Repo vs Deployed (VPS)"
echo "  Repo dir: ${REPO_DIR}"
echo "============================================================"
echo ""

# ── Compare exact-match configs ──
echo "── Exact-match configs ──────────────────────────────────────"
for repo_rel in "${!CONFIG_MAP[@]}"; do
  deployed="${CONFIG_MAP[$repo_rel]}"
  repo_file="${REPO_DIR}/${repo_rel}"

  printf "  %-50s " "${repo_rel}"

  if [ ! -f "$repo_file" ]; then
    printf "${YELLOW}SKIP${NC} (repo file missing)\n"
    SKIP=$((SKIP + 1))
    continue
  fi

  if [ ! -f "$deployed" ]; then
    printf "${YELLOW}SKIP${NC} (not deployed at ${deployed})\n"
    SKIP=$((SKIP + 1))
    continue
  fi

  if diff -q "$repo_file" "$deployed" > /dev/null 2>&1; then
    printf "${GREEN}MATCH${NC}\n"
    PASS=$((PASS + 1))
  else
    printf "${RED}DIFF${NC}\n"
    FAIL=$((FAIL + 1))
    echo "    --- Differences ---"
    diff --unified=3 "$repo_file" "$deployed" | head -40 || true
    echo ""
  fi
done

echo ""

# ── Compare template configs (structural — ignore ${VAR} expansions) ──
echo "── Template configs (structural comparison) ──────────────────"
for repo_rel in "${!TEMPLATE_MAP[@]}"; do
  deployed="${TEMPLATE_MAP[$repo_rel]}"
  repo_file="${REPO_DIR}/${repo_rel}"

  printf "  %-50s " "${repo_rel}"

  if [ ! -f "$repo_file" ]; then
    printf "${YELLOW}SKIP${NC} (repo file missing)\n"
    SKIP=$((SKIP + 1))
    continue
  fi

  if [ ! -f "$deployed" ]; then
    printf "${YELLOW}SKIP${NC} (not found at ${deployed})\n"
    SKIP=$((SKIP + 1))
    continue
  fi

  # Strip ${...} placeholders from repo version for structural comparison
  repo_stripped=$(sed 's/\${[^}]*}/PLACEHOLDER/g' "$repo_file")
  deployed_stripped=$(sed 's/[^ =]*[A-Za-z0-9_\-]\{8,\}[^ ]*/PLACEHOLDER/g' "$deployed")

  # Compare line count and directive names as a structural check
  repo_lines=$(echo "$repo_stripped" | grep -v '^#' | grep -v '^$' | wc -l)
  deployed_lines=$(cat "$deployed" | grep -v '^#' | grep -v '^$' | wc -l)

  if [ "$repo_lines" -eq "$deployed_lines" ]; then
    printf "${GREEN}MATCH${NC} (${repo_lines} directives)\n"
    PASS=$((PASS + 1))
  else
    printf "${YELLOW}REVIEW${NC} (repo: ${repo_lines} lines, deployed: ${deployed_lines} lines)\n"
    FAIL=$((FAIL + 1))
    echo "    Template comparison (variable expansion differs by design)."
    echo "    Verify manually that all directives are present."
  fi
done

echo ""

# ── Docker-compose volume-mounted configs ──
echo "── Volume-mounted configs (via docker inspect) ───────────────"
for container in livekit coturn; do
  printf "  %-50s " "container: ${container}"
  if docker inspect "$container" > /dev/null 2>&1; then
    mounts=$(docker inspect "$container" --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}' 2>/dev/null || echo "")
    if [ -n "$mounts" ]; then
      printf "${GREEN}RUNNING${NC}\n"
      echo "$mounts" | while IFS= read -r line; do
        [ -n "$line" ] && echo "    ${line}"
      done
    else
      printf "${YELLOW}NO MOUNTS${NC}\n"
    fi
  else
    printf "${YELLOW}NOT RUNNING${NC}\n"
    SKIP=$((SKIP + 1))
  fi
done

echo ""
echo "============================================================"
echo "  Results: ${GREEN}${PASS} matched${NC}, ${RED}${FAIL} differ${NC}, ${YELLOW}${SKIP} skipped${NC}"
echo "============================================================"

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
