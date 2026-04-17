#!/bin/bash
# =============================================================
# FULL SYSTEM DEEP TEST + AUDIT
# Date: 2026-04-17
# =============================================================

REDIS_PASS="UuhN4ehSgOTbeDlLltEnJ8R2tYQa8F"
WBOM_KEY="EDFEOdx968OTTlTpZnQzOL1359MEs-6HIV35F948pCA"

echo "=============================================="
echo "  FULL SYSTEM DEEP TEST + AUDIT"
echo "  $(date)"
echo "=============================================="

# =============================================================
# TEST 1: SERVICE HEALTH
# =============================================================
echo ""
echo ">>> TEST 1: SERVICE HEALTH"

echo "[1a] API Gateway..."
API_HEALTH=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8100/health)
echo "  API: HTTP $API_HEALTH"

echo "[1b] WBOM..."
WBOM_HEALTH=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:9900/health)
echo "  WBOM: HTTP $WBOM_HEALTH"

echo "[1c] Brain (via docker network)..."
BRAIN_HEALTH=$(docker exec fazle-wbom python3 -c "
import urllib.request
try:
    r = urllib.request.urlopen('http://fazle-brain:8200/health', timeout=5)
    print(f'HTTP {r.status}')
except Exception as e:
    print(f'FAIL: {e}')
" 2>&1)
echo "  Brain: $BRAIN_HEALTH"

echo "[1d] LLM Gateway..."
LLM_HEALTH=$(docker exec fazle-wbom python3 -c "
import urllib.request
try:
    r = urllib.request.urlopen('http://fazle-llm-gateway:8800/health', timeout=5)
    print(f'HTTP {r.status}')
except Exception as e:
    print(f'FAIL: {e}')
" 2>&1)
echo "  LLM Gateway: $LLM_HEALTH"

echo "[1e] Social Engine..."
SOCIAL_HEALTH=$(docker exec fazle-wbom python3 -c "
import urllib.request
try:
    r = urllib.request.urlopen('http://fazle-social-engine:9800/health', timeout=5)
    print(f'HTTP {r.status}')
except Exception as e:
    print(f'FAIL: {e}')
" 2>&1)
echo "  Social Engine: $SOCIAL_HEALTH"

echo "[1f] Ollama..."
OLLAMA_MODELS=$(docker exec ollama ollama list 2>&1)
echo "  Ollama Models:"
echo "$OLLAMA_MODELS" | sed 's/^/    /'

echo "[1g] PostgreSQL..."
PG_STATUS=$(docker exec ai-postgres pg_isready -U postgres 2>&1)
echo "  PostgreSQL: $PG_STATUS"

echo "[1h] Redis..."
REDIS_PING=$(docker exec ai-redis redis-cli -a "$REDIS_PASS" --no-auth-warning ping 2>&1)
echo "  Redis: $REDIS_PING"

# =============================================================
# TEST 2: AI CORE - Chat Endpoint
# =============================================================
echo ""
echo ">>> TEST 2: AI CORE - Chat Endpoint"

echo "[2a] Salary query (Bangla)..."
cat > /tmp/test_chat1.json << 'EOF'
{"message": "Samir er salary koto?", "user_id": "test-audit-001", "phone": "01700000001"}
EOF
CHAT1=$(curl -s -w '\n__HTTP__%{http_code}__TIME__%{time_total}s' -X POST http://localhost:8100/fazle/chat -H 'Content-Type: application/json' -d @/tmp/test_chat1.json 2>&1)
echo "  Response: $(echo "$CHAT1" | head -c 500)"
echo ""

echo "[2b] English greeting..."
cat > /tmp/test_chat2.json << 'EOF'
{"message": "Hello, how are you?", "user_id": "test-audit-002", "phone": "01700000002"}
EOF
CHAT2=$(curl -s -w '\n__HTTP__%{http_code}__TIME__%{time_total}s' -X POST http://localhost:8100/fazle/chat -H 'Content-Type: application/json' -d @/tmp/test_chat2.json 2>&1)
echo "  Response: $(echo "$CHAT2" | head -c 500)"
echo ""

echo "[2c] Duty query..."
cat > /tmp/test_chat3.json << 'EOF'
{"message": "Kal ke ke duty te ache?", "user_id": "test-audit-003", "phone": "01700000003"}
EOF
CHAT3=$(curl -s -w '\n__HTTP__%{http_code}__TIME__%{time_total}s' -X POST http://localhost:8100/fazle/chat -H 'Content-Type: application/json' -d @/tmp/test_chat3.json 2>&1)
echo "  Response: $(echo "$CHAT3" | head -c 500)"
echo ""

# =============================================================
# TEST 3: WBOM ENDPOINTS (with internal key)
# =============================================================
echo ""
echo ">>> TEST 3: WBOM CRUD ENDPOINTS"

echo "[3a] WBOM Contacts list..."
CONTACTS=$(curl -s -w '\n__HTTP__%{http_code}' http://localhost:9900/api/wbom/contacts -H "X-Internal-Key: $WBOM_KEY" 2>&1)
CONTACTS_CODE=$(echo "$CONTACTS" | grep '__HTTP__' | sed 's/__HTTP__//')
CONTACTS_COUNT=$(echo "$CONTACTS" | head -1 | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d) if isinstance(d,list) else d.get('total',d.get('count','?')))" 2>/dev/null || echo "parse_error")
echo "  HTTP: $CONTACTS_CODE | Count: $CONTACTS_COUNT"

echo "[3b] WBOM Employees list..."
EMPLOYEES=$(curl -s -w '\n__HTTP__%{http_code}' http://localhost:9900/api/wbom/employees -H "X-Internal-Key: $WBOM_KEY" 2>&1)
EMP_CODE=$(echo "$EMPLOYEES" | grep '__HTTP__' | sed 's/__HTTP__//')
EMP_COUNT=$(echo "$EMPLOYEES" | head -1 | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d) if isinstance(d,list) else d.get('total',d.get('count','?')))" 2>/dev/null || echo "parse_error")
echo "  HTTP: $EMP_CODE | Count: $EMP_COUNT"

echo "[3c] WBOM Transactions list..."
TXNS=$(curl -s -w '\n__HTTP__%{http_code}' http://localhost:9900/api/wbom/transactions -H "X-Internal-Key: $WBOM_KEY" 2>&1)
TXN_CODE=$(echo "$TXNS" | grep '__HTTP__' | sed 's/__HTTP__//')
TXN_COUNT=$(echo "$TXNS" | head -1 | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d) if isinstance(d,list) else d.get('total',d.get('count','?')))" 2>/dev/null || echo "parse_error")
echo "  HTTP: $TXN_CODE | Count: $TXN_COUNT"

echo "[3d] WBOM Programs..."
PROGS=$(curl -s -w '\n__HTTP__%{http_code}' http://localhost:9900/api/wbom/programs -H "X-Internal-Key: $WBOM_KEY" 2>&1)
PROG_CODE=$(echo "$PROGS" | grep '__HTTP__' | sed 's/__HTTP__//')
echo "  HTTP: $PROG_CODE"

echo "[3e] WBOM Search..."
cat > /tmp/test_search.json << 'EOF'
{"query": "Samir", "tables": ["contacts", "employees"]}
EOF
SEARCH=$(curl -s -w '\n__HTTP__%{http_code}' -X POST http://localhost:9900/api/wbom/search -H "X-Internal-Key: $WBOM_KEY" -H 'Content-Type: application/json' -d @/tmp/test_search.json 2>&1)
SEARCH_CODE=$(echo "$SEARCH" | grep '__HTTP__' | sed 's/__HTTP__//')
echo "  HTTP: $SEARCH_CODE | Response: $(echo "$SEARCH" | head -1 | head -c 300)"

echo "[3f] WBOM without auth key (should fail)..."
NOAUTH=$(curl -s -w '\n__HTTP__%{http_code}' http://localhost:9900/api/wbom/contacts 2>&1)
NOAUTH_CODE=$(echo "$NOAUTH" | grep '__HTTP__' | sed 's/__HTTP__//')
echo "  Without key: HTTP $NOAUTH_CODE (expected: 403)"

echo "[3g] WBOM with wrong auth key (should fail)..."
WRONGAUTH=$(curl -s -w '\n__HTTP__%{http_code}' http://localhost:9900/api/wbom/contacts -H "X-Internal-Key: wrong-key-12345" 2>&1)
WRONGAUTH_CODE=$(echo "$WRONGAUTH" | grep '__HTTP__' | sed 's/__HTTP__//')
echo "  Wrong key: HTTP $WRONGAUTH_CODE (expected: 403)"

# =============================================================
# TEST 4: PAYMENT FLOW
# =============================================================
echo ""
echo ">>> TEST 4: PAYMENT FLOW"

echo "[4a] Payment via chat..."
cat > /tmp/test_pay.json << 'EOF'
{"message": "Karim ke 1000 taka dao bkash e", "user_id": "test-audit-pay-001", "phone": "01700000099"}
EOF
PAY=$(curl -s -w '\n__HTTP__%{http_code}__TIME__%{time_total}s' -X POST http://localhost:8100/fazle/chat -H 'Content-Type: application/json' -d @/tmp/test_pay.json 2>&1)
echo "  Response: $(echo "$PAY" | head -c 600)"
echo ""

# =============================================================
# TEST 5: EMPLOYEE INTERACTION
# =============================================================
echo ""
echo ">>> TEST 5: EMPLOYEE INTERACTION"

echo "[5a] Employee asking about balance..."
cat > /tmp/test_emp.json << 'EOF'
{"message": "Sir amar taka baki koto?", "user_id": "test-audit-emp-001", "phone": "01700000088"}
EOF
EMP=$(curl -s -w '\n__HTTP__%{http_code}__TIME__%{time_total}s' -X POST http://localhost:8100/fazle/chat -H 'Content-Type: application/json' -d @/tmp/test_emp.json 2>&1)
echo "  Response: $(echo "$EMP" | head -c 500)"
echo ""

# =============================================================
# TEST 6: CLIENT/JOB SEEKER
# =============================================================
echo ""
echo ">>> TEST 6: CLIENT / JOB SEEKER"

echo "[6a] Rate inquiry..."
cat > /tmp/test_client.json << 'EOF'
{"message": "Security guard rate koto?", "user_id": "test-audit-client-001", "phone": "01700000077"}
EOF
CLIENT=$(curl -s -w '\n__HTTP__%{http_code}__TIME__%{time_total}s' -X POST http://localhost:8100/fazle/chat -H 'Content-Type: application/json' -d @/tmp/test_client.json 2>&1)
echo "  Response: $(echo "$CLIENT" | head -c 500)"
echo ""

echo "[6b] Job application..."
cat > /tmp/test_job.json << 'EOF'
{"message": "Ami security guard er chakri korte chai. Amar boyos 28.", "user_id": "test-audit-job-001", "phone": "01700000066"}
EOF
JOB=$(curl -s -w '\n__HTTP__%{http_code}__TIME__%{time_total}s' -X POST http://localhost:8100/fazle/chat -H 'Content-Type: application/json' -d @/tmp/test_job.json 2>&1)
echo "  Response: $(echo "$JOB" | head -c 500)"
echo ""

# =============================================================
# TEST 7: DATABASE VALIDATION
# =============================================================
echo ""
echo ">>> TEST 7: DATABASE VALIDATION"

echo "[7a] Table row counts..."
docker exec ai-postgres psql -U postgres -d ai_platform -t -c "
SELECT 'wbom_contacts' as tbl, count(*) FROM wbom_contacts
UNION ALL SELECT 'wbom_employees', count(*) FROM wbom_employees
UNION ALL SELECT 'wbom_escort_programs', count(*) FROM wbom_escort_programs
UNION ALL SELECT 'wbom_cash_transactions', count(*) FROM wbom_cash_transactions
UNION ALL SELECT 'wbom_billing_records', count(*) FROM wbom_billing_records
UNION ALL SELECT 'wbom_salary_records', count(*) FROM wbom_salary_records
UNION ALL SELECT 'wbom_whatsapp_messages', count(*) FROM wbom_whatsapp_messages
UNION ALL SELECT 'wbom_extracted_data', count(*) FROM wbom_extracted_data
UNION ALL SELECT 'wbom_message_templates', count(*) FROM wbom_message_templates
UNION ALL SELECT 'wbom_relation_types', count(*) FROM wbom_relation_types
UNION ALL SELECT 'wbom_business_types', count(*) FROM wbom_business_types
UNION ALL SELECT 'wbom_contact_templates', count(*) FROM wbom_contact_templates
ORDER BY 1;
" 2>&1

echo ""
echo "[7b] Duplicate transaction check..."
docker exec ai-postgres psql -U postgres -d ai_platform -t -c "
SELECT employee_id, transaction_date, amount, transaction_type, payment_method, count(*) as dupes
FROM wbom_cash_transactions
WHERE status = 'Completed'
GROUP BY employee_id, transaction_date, amount, transaction_type, payment_method
HAVING count(*) > 1
ORDER BY dupes DESC
LIMIT 10;
" 2>&1

echo ""
echo "[7c] Orphan records check..."
docker exec ai-postgres psql -U postgres -d ai_platform -t -c "
SELECT 'orphan_transactions' as check_type, count(*) FROM wbom_cash_transactions ct
WHERE ct.employee_id IS NOT NULL AND ct.employee_id NOT IN (SELECT id FROM wbom_employees)
UNION ALL
SELECT 'orphan_escort_programs', count(*) FROM wbom_escort_programs ep
WHERE ep.employee_id IS NOT NULL AND ep.employee_id NOT IN (SELECT id FROM wbom_employees)
UNION ALL
SELECT 'orphan_billing', count(*) FROM wbom_billing_records br
WHERE br.employee_id IS NOT NULL AND br.employee_id NOT IN (SELECT id FROM wbom_employees);
" 2>&1

echo ""
echo "[7d] NULL critical fields..."
docker exec ai-postgres psql -U postgres -d ai_platform -t -c "
SELECT 'txn_null_amount' as check_type, count(*) FROM wbom_cash_transactions WHERE amount IS NULL
UNION ALL SELECT 'txn_null_employee', count(*) FROM wbom_cash_transactions WHERE employee_id IS NULL
UNION ALL SELECT 'emp_null_name', count(*) FROM wbom_employees WHERE name IS NULL OR name = ''
UNION ALL SELECT 'contact_null_phone', count(*) FROM wbom_contacts WHERE phone IS NULL OR phone = '';
" 2>&1

echo ""
echo "[7e] Index check on critical tables..."
docker exec ai-postgres psql -U postgres -d ai_platform -t -c "
SELECT indexname, tablename FROM pg_indexes 
WHERE tablename LIKE 'wbom_%' 
ORDER BY tablename, indexname;
" 2>&1

# =============================================================
# TEST 8: RETRY QUEUE / REDIS STATE
# =============================================================
echo ""
echo ">>> TEST 8: RETRY QUEUE / REDIS"

echo "[8a] Retry queue length..."
docker exec ai-redis redis-cli -a "$REDIS_PASS" --no-auth-warning LLEN wbom_retry_queue 2>&1
echo "[8b] DLQ length..."
docker exec ai-redis redis-cli -a "$REDIS_PASS" --no-auth-warning LLEN wbom_dlq 2>&1
echo "[8c] Dedup keys (db5)..."
docker exec ai-redis redis-cli -a "$REDIS_PASS" --no-auth-warning -n 5 DBSIZE 2>&1
echo "[8d] Rate limit keys (db6)..."
docker exec ai-redis redis-cli -a "$REDIS_PASS" --no-auth-warning -n 6 DBSIZE 2>&1
echo "[8e] Conversation memory keys (db1)..."
docker exec ai-redis redis-cli -a "$REDIS_PASS" --no-auth-warning -n 1 DBSIZE 2>&1
echo "[8f] Sample conversation keys..."
docker exec ai-redis redis-cli -a "$REDIS_PASS" --no-auth-warning -n 1 KEYS '*' 2>&1 | head -10

# =============================================================
# TEST 9: ERROR HANDLING
# =============================================================
echo ""
echo ">>> TEST 9: ERROR HANDLING"

echo "[9a] Invalid payment amount..."
cat > /tmp/test_invalid_pay.json << 'EOF'
{"message": "Karim ke -500 taka dao", "user_id": "test-audit-err-001", "phone": "01700000055"}
EOF
INVALID_PAY=$(curl -s -w '\n__HTTP__%{http_code}' -X POST http://localhost:8100/fazle/chat -H 'Content-Type: application/json' -d @/tmp/test_invalid_pay.json 2>&1)
echo "  Response: $(echo "$INVALID_PAY" | head -c 400)"
echo ""

echo "[9b] Empty message..."
cat > /tmp/test_empty.json << 'EOF'
{"message": "", "user_id": "test-audit-err-002", "phone": "01700000054"}
EOF
EMPTY=$(curl -s -w '\n__HTTP__%{http_code}' -X POST http://localhost:8100/fazle/chat -H 'Content-Type: application/json' -d @/tmp/test_empty.json 2>&1)
echo "  Response: $(echo "$EMPTY" | head -c 400)"
echo ""

echo "[9c] Missing required fields..."
MISSING=$(curl -s -w '\n__HTTP__%{http_code}' -X POST http://localhost:8100/fazle/chat -H 'Content-Type: application/json' -d '{}' 2>&1)
echo "  Response: $(echo "$MISSING" | head -c 400)"
echo ""

echo "[9d] Malformed JSON..."
MALFORMED=$(curl -s -w '\n__HTTP__%{http_code}' -X POST http://localhost:8100/fazle/chat -H 'Content-Type: application/json' -d 'not-json' 2>&1)
echo "  Response: $(echo "$MALFORMED" | head -c 400)"
echo ""

# =============================================================
# TEST 10: LOGGING & TRACE
# =============================================================
echo ""
echo ">>> TEST 10: LOGGING & TRACE"

echo "[10a] Recent API logs..."
docker logs fazle-api --since=5m --tail=20 2>&1 | head -40
echo ""

echo "[10b] Recent Brain logs..."
docker logs fazle-brain --since=5m --tail=20 2>&1 | head -40
echo ""

echo "[10c] Recent WBOM logs..."
docker logs fazle-wbom --since=5m --tail=20 2>&1 | head -40
echo ""

echo "[10d] Recent Social Engine logs..."
docker logs fazle-social-engine --since=5m --tail=20 2>&1 | head -40

# =============================================================
# TEST 11: DOMAIN ROUTING
# =============================================================
echo ""
echo ">>> TEST 11: DOMAIN ROUTING (External)"

echo "[11a] iamazim.com..."
curl -s -o /dev/null -w 'HTTP %{http_code}' https://iamazim.com 2>&1
echo ""
echo "[11b] fazle.iamazim.com..."
curl -s -o /dev/null -w 'HTTP %{http_code}' https://fazle.iamazim.com 2>&1
echo ""
echo "[11c] api.iamazim.com health..."
curl -s -w '\nHTTP %{http_code}' https://api.iamazim.com/health 2>&1
echo ""
echo "[11d] api.iamazim.com WBOM (with key)..."
curl -s -w '\nHTTP %{http_code}' https://api.iamazim.com/api/wbom/contacts -H "X-Internal-Key: $WBOM_KEY" 2>&1 | tail -3
echo ""
echo "[11e] api.iamazim.com WBOM (no key, should 403)..."
curl -s -w '\nHTTP %{http_code}' https://api.iamazim.com/api/wbom/contacts 2>&1 | tail -3
echo ""

# =============================================================
# CLEANUP
# =============================================================
rm -f /tmp/test_*.json

echo ""
echo "=============================================="
echo "  AUDIT TESTS COMPLETE: $(date)"
echo "=============================================="
