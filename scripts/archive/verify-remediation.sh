#!/bin/bash
echo "=== POST-REMEDIATION VERIFICATION ==="
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""
ERRORS=0
FIXED=0

# 1. P0-SEC-1: gen-secrets.sh generates 11 secrets
COUNT=$(grep -c "openssl rand" gen-secrets.sh 2>/dev/null || echo 0)
if [ "$COUNT" -eq 11 ]; then
    echo "  [PASS] P0-SEC-1: gen-secrets.sh generates $COUNT secrets"
    FIXED=$((FIXED+1))
else
    echo "  [FAIL] P0-SEC-1: gen-secrets.sh generates $COUNT secrets (expected 11)"
    ERRORS=$((ERRORS+1))
fi

# 2. P0-SEC-1b: No cleartext secret echo
if grep -qE 'echo.*\$\{?(PG_PASS|REDIS_PASS|MINIO_PASS)\}?' gen-secrets.sh 2>/dev/null; then
    echo "  [FAIL] P0-SEC-1b: Still echoing secrets in cleartext"
    ERRORS=$((ERRORS+1))
else
    echo "  [PASS] P0-SEC-1b: Secret output suppressed"
    FIXED=$((FIXED+1))
fi

# 3. P0-SEC-2: safety.py fail-closed for children
if grep -q 'daughter.*son.*child' fazle-system/brain/safety.py 2>/dev/null; then
    echo "  [PASS] P0-SEC-2: Fail-closed for child accounts"
    FIXED=$((FIXED+1))
else
    echo "  [FAIL] P0-SEC-2: Missing fail-closed logic for children"
    ERRORS=$((ERRORS+1))
fi

# 4. P1-SEC-3: FastAPI docs disabled
if grep -q 'docs_url=None' fazle-system/api/main.py 2>/dev/null; then
    echo "  [PASS] P1-SEC-3: FastAPI docs disabled"
    FIXED=$((FIXED+1))
else
    echo "  [FAIL] P1-SEC-3: FastAPI docs still exposed"
    ERRORS=$((ERRORS+1))
fi

# 5. P1-SEC-4: Nginx docs blocked
if grep -q 'deny all' configs/nginx/fazle.iamazim.com.conf 2>/dev/null; then
    echo "  [PASS] P1-SEC-4: Nginx /docs blocked"
    FIXED=$((FIXED+1))
else
    echo "  [FAIL] P1-SEC-4: Nginx still proxies /docs publicly"
    ERRORS=$((ERRORS+1))
fi

# 6. P1-SEC-6: Timing-safe comparison
if grep -q 'hmac.compare_digest' fazle-system/api/main.py 2>/dev/null; then
    echo "  [PASS] P1-SEC-6: Timing-safe API key comparison"
    FIXED=$((FIXED+1))
else
    echo "  [FAIL] P1-SEC-6: Still using == for API key comparison"
    ERRORS=$((ERRORS+1))
fi

# 7. P1-SEC-7: No stale .next build cache
if [ -d "fazle-system/ui/.next" ]; then
    echo "  [FAIL] P1-SEC-7: .next cache still exists"
    ERRORS=$((ERRORS+1))
else
    echo "  [PASS] P1-SEC-7: .next build cache removed"
    FIXED=$((FIXED+1))
fi

# 8. P1-SEC-8: FAZLE_API_KEY fail-fast
if grep -q 'FAZLE_API_KEY.*:?' docker-compose.yaml 2>/dev/null; then
    echo "  [PASS] P1-SEC-8: FAZLE_API_KEY uses fail-fast"
    FIXED=$((FIXED+1))
else
    echo "  [FAIL] P1-SEC-8: FAZLE_API_KEY still uses :- fallback"
    ERRORS=$((ERRORS+1))
fi

# 9. P1-SEC-9: SSRF protection
if grep -q '_is_private_ip' fazle-system/tools/main.py 2>/dev/null; then
    echo "  [PASS] P1-SEC-9: SSRF protection present"
    FIXED=$((FIXED+1))
else
    echo "  [FAIL] P1-SEC-9: Missing SSRF protection"
    ERRORS=$((ERRORS+1))
fi

# 10. P1-NET-1: WebSocket headers
if grep -q 'proxy_set_header Upgrade' configs/nginx/fazle.iamazim.com.conf 2>/dev/null; then
    echo "  [PASS] P1-NET-1: WebSocket upgrade headers present"
    FIXED=$((FIXED+1))
else
    echo "  [FAIL] P1-NET-1: Missing WebSocket headers"
    ERRORS=$((ERRORS+1))
fi

# 11. P1-DEP-1: Missing Python packages
if grep -q 'PyPDF2' fazle-system/api/requirements.txt 2>/dev/null && \
   grep -q 'python-docx' fazle-system/api/requirements.txt 2>/dev/null; then
    echo "  [PASS] P1-DEP-1: PyPDF2 and python-docx added"
    FIXED=$((FIXED+1))
else
    echo "  [FAIL] P1-DEP-1: Missing PyPDF2 or python-docx"
    ERRORS=$((ERRORS+1))
fi

# 12. P1-DEP-2: Outdated JWT library replaced
if grep -q 'PyJWT' fazle-system/api/requirements.txt 2>/dev/null && \
   ! grep -q 'python-jose' fazle-system/api/requirements.txt 2>/dev/null; then
    echo "  [PASS] P1-DEP-2: python-jose replaced with PyJWT"
    FIXED=$((FIXED+1))
else
    echo "  [FAIL] P1-DEP-2: Still using python-jose"
    ERRORS=$((ERRORS+1))
fi

# 13. P1-OPS-1: Pinned image tags
if ! grep -q ':latest' docker-compose.yaml 2>/dev/null; then
    echo "  [PASS] P1-OPS-1: No :latest tags found"
    FIXED=$((FIXED+1))
else
    echo "  [FAIL] P1-OPS-1: :latest tags still present"
    ERRORS=$((ERRORS+1))
fi

# 14. P1-OPS-2: Loki healthcheck
if grep -q 'wget.*3100/ready' docker-compose.yaml 2>/dev/null; then
    echo "  [PASS] P1-OPS-2: Loki healthcheck uses /ready"
    FIXED=$((FIXED+1))
else
    echo "  [FAIL] P1-OPS-2: Loki healthcheck is weak"
    ERRORS=$((ERRORS+1))
fi

# 15. P1-OPS-3: Connection pooling
if grep -q 'ThreadedConnectionPool' fazle-system/api/database.py 2>/dev/null; then
    echo "  [PASS] P1-OPS-3: Connection pooling enabled"
    FIXED=$((FIXED+1))
else
    echo "  [FAIL] P1-OPS-3: No connection pooling"
    ERRORS=$((ERRORS+1))
fi

# 16. P1-OPS-4: Prometheus metrics on secondary services
METRICS_OK=true
for svc in brain memory tasks tools; do
    if ! grep -q 'Instrumentator' "fazle-system/$svc/main.py" 2>/dev/null; then
        METRICS_OK=false
        break
    fi
done
if [ "$METRICS_OK" = true ]; then
    echo "  [PASS] P1-OPS-4: Prometheus metrics on all services"
    FIXED=$((FIXED+1))
else
    echo "  [FAIL] P1-OPS-4: Missing Prometheus metrics on some services"
    ERRORS=$((ERRORS+1))
fi

echo ""
echo "=== PHASE 6 — THREE-STACK LAYOUT ==="

# P6-1: Three-stack compose files exist
for stack in ai-infra dograh fazle-ai; do
    if [ -f "$stack/docker-compose.yaml" ]; then
        echo "  [PASS] P6-STACK: $stack/docker-compose.yaml exists"
        FIXED=$((FIXED+1))
    else
        echo "  [FAIL] P6-STACK: $stack/docker-compose.yaml missing"
        ERRORS=$((ERRORS+1))
    fi
done

# P6-2: restart: unless-stopped in all three stacks
for stack in ai-infra dograh fazle-ai; do
    if [ -f "$stack/docker-compose.yaml" ]; then
        BAD=$(grep -c 'restart: always' "$stack/docker-compose.yaml" 2>/dev/null || echo 0)
        if [ "$BAD" -eq 0 ]; then
            echo "  [PASS] P6-RESTART: $stack uses unless-stopped"
            FIXED=$((FIXED+1))
        else
            echo "  [FAIL] P6-RESTART: $stack has $BAD services with restart: always"
            ERRORS=$((ERRORS+1))
        fi
    fi
done

# P6-3: Redis persistence flags
if grep -q 'appendfsync everysec' ai-infra/docker-compose.yaml 2>/dev/null; then
    echo "  [PASS] P6-REDIS: AOF appendfsync enabled"
    FIXED=$((FIXED+1))
else
    echo "  [FAIL] P6-REDIS: Missing appendfsync in Redis config"
    ERRORS=$((ERRORS+1))
fi

# P6-4: Grafana dashboard provisioning
if [ -f "configs/grafana/provisioning/dashboards/dashboards.yml" ]; then
    echo "  [PASS] P6-GRAFANA: Dashboard provisioning configured"
    FIXED=$((FIXED+1))
else
    echo "  [FAIL] P6-GRAFANA: Missing dashboard provisioning"
    ERRORS=$((ERRORS+1))
fi

# P6-5: Stack management scripts exist
for script in create-networks.sh stack-up.sh stack-down.sh stack-status.sh; do
    if [ -f "scripts/$script" ]; then
        echo "  [PASS] P6-SCRIPTS: scripts/$script exists"
        FIXED=$((FIXED+1))
    else
        echo "  [FAIL] P6-SCRIPTS: scripts/$script missing"
        ERRORS=$((ERRORS+1))
    fi
done

# P6-6: Health endpoints return proper HTTP status codes
if grep -q 'JSONResponse' fazle-system/queue/main.py 2>/dev/null && \
   grep -q 'JSONResponse' fazle-system/workers/main.py 2>/dev/null; then
    echo "  [PASS] P6-HEALTH: Queue/Workers return proper HTTP status codes"
    FIXED=$((FIXED+1))
else
    echo "  [FAIL] P6-HEALTH: Queue/Workers missing JSONResponse for health"
    ERRORS=$((ERRORS+1))
fi

echo ""
echo "=== SUMMARY ==="
echo "  Fixed: $FIXED checks passed"
echo "  Errors: $ERRORS"
echo ""
if [ $ERRORS -eq 0 ]; then
    echo "  ALL CHECKS PASSED — Safe to deploy"
else
    echo "  $ERRORS ISSUES REMAIN — Do not deploy"
fi
exit $ERRORS
