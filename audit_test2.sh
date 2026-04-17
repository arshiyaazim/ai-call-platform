#!/bin/bash
# DB + AUTH TESTS
FAZLE_KEY="2aMFFfIaGDfgfP6JiXaevEgMRx9aZtgAzYriHGRcpvdEcWCtp7Xpqul0BYdjFchq"
WBOM_KEY="EDFEOdx968OTTlTpZnQzOL1359MEs-6HIV35F948pCA"
REDIS_PASS="UuhN4ehSgOTbeDlLltEnJ8R2tYQa8F"

echo "=== DB TABLES (default postgres db) ==="
docker exec ai-postgres psql -U postgres -t -c "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'wbom_%' ORDER BY tablename"

echo ""
echo "=== TABLE ROW COUNTS ==="
docker exec ai-postgres psql -U postgres -t -c "
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
"

echo ""
echo "=== DUPLICATE TRANSACTIONS ==="
docker exec ai-postgres psql -U postgres -t -c "
SELECT employee_id, transaction_date, amount, transaction_type, payment_method, count(*) as dupes
FROM wbom_cash_transactions
WHERE status = 'Completed'
GROUP BY employee_id, transaction_date, amount, transaction_type, payment_method
HAVING count(*) > 1
ORDER BY dupes DESC
LIMIT 10;
"

echo ""
echo "=== ORPHAN RECORDS ==="
docker exec ai-postgres psql -U postgres -t -c "
SELECT 'orphan_transactions' as check_type, count(*) FROM wbom_cash_transactions ct
WHERE ct.employee_id IS NOT NULL AND ct.employee_id NOT IN (SELECT id FROM wbom_employees)
UNION ALL
SELECT 'orphan_escort_programs', count(*) FROM wbom_escort_programs ep
WHERE ep.employee_id IS NOT NULL AND ep.employee_id NOT IN (SELECT id FROM wbom_employees)
UNION ALL
SELECT 'orphan_billing', count(*) FROM wbom_billing_records br
WHERE br.employee_id IS NOT NULL AND br.employee_id NOT IN (SELECT id FROM wbom_employees);
"

echo ""
echo "=== NULL CRITICAL FIELDS ==="
docker exec ai-postgres psql -U postgres -t -c "
SELECT 'txn_null_amount' as chk, count(*) FROM wbom_cash_transactions WHERE amount IS NULL
UNION ALL SELECT 'txn_null_employee', count(*) FROM wbom_cash_transactions WHERE employee_id IS NULL
UNION ALL SELECT 'emp_null_name', count(*) FROM wbom_employees WHERE name IS NULL OR name = ''
UNION ALL SELECT 'contact_null_phone', count(*) FROM wbom_contacts WHERE phone IS NULL OR phone = '';
"

echo ""
echo "=== INDEXES ON WBOM TABLES ==="
docker exec ai-postgres psql -U postgres -t -c "
SELECT indexname, tablename FROM pg_indexes 
WHERE tablename LIKE 'wbom_%' 
ORDER BY tablename, indexname;
"

echo ""
echo "=== ALL FAZLE/WBOM TABLES ==="
docker exec ai-postgres psql -U postgres -t -c "
SELECT tablename FROM pg_tables 
WHERE schemaname='public' 
ORDER BY tablename;
"

echo ""
echo "=========================================="
echo "  AI CORE TESTS (with auth)"
echo "=========================================="

echo "[CHAT-1] Salary query..."
cat > /tmp/tc1.json << 'EOF'
{"message": "Samir er salary koto?", "user_id": "test-audit-001", "phone": "01700000001"}
EOF
curl -s -w '\n[HTTP %{http_code}] [Time: %{time_total}s]' -X POST http://localhost:8100/fazle/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $FAZLE_KEY" \
  -d @/tmp/tc1.json 2>&1 | head -c 1000
echo ""

echo ""
echo "[CHAT-2] English greeting..."
cat > /tmp/tc2.json << 'EOF'
{"message": "Hello, how are you?", "user_id": "test-audit-002", "phone": "01700000002"}
EOF
curl -s -w '\n[HTTP %{http_code}] [Time: %{time_total}s]' -X POST http://localhost:8100/fazle/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $FAZLE_KEY" \
  -d @/tmp/tc2.json 2>&1 | head -c 1000
echo ""

echo ""
echo "[CHAT-3] Duty query..."
cat > /tmp/tc3.json << 'EOF'
{"message": "Kal ke ke duty te ache?", "user_id": "test-audit-003", "phone": "01700000003"}
EOF
curl -s -w '\n[HTTP %{http_code}] [Time: %{time_total}s]' -X POST http://localhost:8100/fazle/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $FAZLE_KEY" \
  -d @/tmp/tc3.json 2>&1 | head -c 1000
echo ""

echo ""
echo "[CHAT-4] Payment request..."
cat > /tmp/tc4.json << 'EOF'
{"message": "Karim ke 1000 taka dao bkash e", "user_id": "test-audit-pay-001", "phone": "01700000099"}
EOF
curl -s -w '\n[HTTP %{http_code}] [Time: %{time_total}s]' -X POST http://localhost:8100/fazle/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $FAZLE_KEY" \
  -d @/tmp/tc4.json 2>&1 | head -c 1000
echo ""

echo ""
echo "[CHAT-5] Employee balance inquiry..."
cat > /tmp/tc5.json << 'EOF'
{"message": "Sir amar taka baki koto?", "user_id": "test-audit-emp-001", "phone": "01700000088"}
EOF
curl -s -w '\n[HTTP %{http_code}] [Time: %{time_total}s]' -X POST http://localhost:8100/fazle/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $FAZLE_KEY" \
  -d @/tmp/tc5.json 2>&1 | head -c 1000
echo ""

echo ""
echo "[CHAT-6] Client rate inquiry..."
cat > /tmp/tc6.json << 'EOF'
{"message": "Security guard rate koto?", "user_id": "test-audit-client-001", "phone": "01700000077"}
EOF
curl -s -w '\n[HTTP %{http_code}] [Time: %{time_total}s]' -X POST http://localhost:8100/fazle/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $FAZLE_KEY" \
  -d @/tmp/tc6.json 2>&1 | head -c 1000
echo ""

echo ""
echo "[CHAT-7] Job application..."
cat > /tmp/tc7.json << 'EOF'
{"message": "Ami security guard er chakri korte chai. Amar boyos 28.", "user_id": "test-audit-job-001", "phone": "01700000066"}
EOF
curl -s -w '\n[HTTP %{http_code}] [Time: %{time_total}s]' -X POST http://localhost:8100/fazle/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $FAZLE_KEY" \
  -d @/tmp/tc7.json 2>&1 | head -c 1000
echo ""

echo ""
echo "[CHAT-8] Invalid negative payment..."
cat > /tmp/tc8.json << 'EOF'
{"message": "Karim ke -500 taka dao", "user_id": "test-audit-err-001", "phone": "01700000055"}
EOF
curl -s -w '\n[HTTP %{http_code}] [Time: %{time_total}s]' -X POST http://localhost:8100/fazle/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $FAZLE_KEY" \
  -d @/tmp/tc8.json 2>&1 | head -c 1000
echo ""

echo ""
echo "[CHAT-9] Empty message..."
cat > /tmp/tc9.json << 'EOF'
{"message": "", "user_id": "test-audit-err-002", "phone": "01700000054"}
EOF
curl -s -w '\n[HTTP %{http_code}] [Time: %{time_total}s]' -X POST http://localhost:8100/fazle/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $FAZLE_KEY" \
  -d @/tmp/tc9.json 2>&1 | head -c 1000
echo ""

echo ""
echo "=========================================="
echo "  OWNER CONTROL TESTS"
echo "=========================================="

echo "[OWNER-1] Owner status query..."
cat > /tmp/to1.json << 'EOF'
{"message": "system status dekhao", "user_id": "owner-azim", "phone": "01958122300"}
EOF
curl -s -w '\n[HTTP %{http_code}] [Time: %{time_total}s]' -X POST http://localhost:8100/fazle/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $FAZLE_KEY" \
  -d @/tmp/to1.json 2>&1 | head -c 1000
echo ""

echo ""
echo "=========================================="
echo "  WBOM SUBAGENT DIRECT TEST"
echo "=========================================="

echo "[WBOM-SUB-1] Process payment message..."
cat > /tmp/tw1.json << 'EOF'
{"message": "Rahim ke 500 taka diyechi bkash e", "sender_phone": "01958122300", "message_id": "test-msg-audit-001"}
EOF
curl -s -w '\n[HTTP %{http_code}] [Time: %{time_total}s]' -X POST http://localhost:9900/api/subagent/wbom/process-message \
  -H "Content-Type: application/json" \
  -H "X-Internal-Key: $WBOM_KEY" \
  -d @/tmp/tw1.json 2>&1 | head -c 1000
echo ""

echo ""
echo "=========================================="
echo "  BRAIN LOGS AFTER AI TESTS"
echo "=========================================="
docker logs fazle-brain --since=3m --tail=30 2>&1 | head -60

echo ""
echo "=========================================="
echo "  API LOGS AFTER AI TESTS"
echo "=========================================="
docker logs fazle-api --since=3m --tail=30 2>&1 | head -60

echo ""
echo "=========================================="
echo "  WBOM LOGS AFTER TESTS"
echo "=========================================="
docker logs fazle-wbom --since=3m --tail=30 2>&1 | head -60

# CLEANUP
rm -f /tmp/tc*.json /tmp/to*.json /tmp/tw*.json

echo ""
echo "=========================================="
echo "  PHASE 2 TESTS COMPLETE: $(date)"
echo "=========================================="
