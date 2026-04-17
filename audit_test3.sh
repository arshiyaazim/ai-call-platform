#!/bin/bash
echo "=== WBOM EMPLOYEES COLUMNS ==="
docker exec ai-postgres psql -U postgres -t -c "SELECT column_name FROM information_schema.columns WHERE table_name='wbom_employees' ORDER BY ordinal_position"

echo "=== WBOM CASH_TRANSACTIONS COLUMNS ==="
docker exec ai-postgres psql -U postgres -t -c "SELECT column_name FROM information_schema.columns WHERE table_name='wbom_cash_transactions' ORDER BY ordinal_position"

echo "=== WBOM STAGING PAYMENTS COLUMNS ==="
docker exec ai-postgres psql -U postgres -t -c "SELECT column_name FROM information_schema.columns WHERE table_name='wbom_staging_payments' ORDER BY ordinal_position"

echo "=== WBOM REJECTED PAYMENTS COLUMNS ==="
docker exec ai-postgres psql -U postgres -t -c "SELECT column_name FROM information_schema.columns WHERE table_name='wbom_rejected_payments' ORDER BY ordinal_position"

echo ""
echo "=== ORPHAN TRANSACTIONS (employee_id not in employees) ==="
docker exec ai-postgres psql -U postgres -t -c "
SELECT 'orphan_txn' as chk, count(*) FROM wbom_cash_transactions ct
WHERE ct.employee_id IS NOT NULL AND ct.employee_id NOT IN (SELECT employee_id FROM wbom_employees)
"

echo ""
echo "=== NULL CHECKS ==="
docker exec ai-postgres psql -U postgres -t -c "
SELECT 'txn_null_amount' as chk, count(*) FROM wbom_cash_transactions WHERE amount IS NULL
UNION ALL SELECT 'txn_null_emp', count(*) FROM wbom_cash_transactions WHERE employee_id IS NULL
UNION ALL SELECT 'emp_null_name', count(*) FROM wbom_employees WHERE employee_name IS NULL OR employee_name = ''
UNION ALL SELECT 'contact_null_phone', count(*) FROM wbom_contacts WHERE whatsapp_number IS NULL OR whatsapp_number = ''
"

echo ""
echo "=== STAGING PAYMENT COUNTS ==="
docker exec ai-postgres psql -U postgres -t -c "SELECT status, count(*) FROM wbom_staging_payments GROUP BY status"

echo ""
echo "=== REJECTED PAYMENT COUNTS ==="
docker exec ai-postgres psql -U postgres -t -c "SELECT reviewed, count(*) FROM wbom_rejected_payments GROUP BY reviewed"

echo ""
echo "=== TRANSACTION DEDUP INDEX DEFINITION ==="
docker exec ai-postgres psql -U postgres -t -c "SELECT indexdef FROM pg_indexes WHERE indexname = 'idx_wbom_transactions_dedup'"

echo ""
echo "=== WA MSG DEDUP INDEX DEFINITION ==="
docker exec ai-postgres psql -U postgres -t -c "SELECT indexdef FROM pg_indexes WHERE indexname = 'idx_wbom_transactions_wa_msg_dedup'"

echo ""
echo "=== SAMPLE TRANSACTIONS (last 5) ==="
docker exec ai-postgres psql -U postgres -t -c "SELECT transaction_id, employee_id, amount, transaction_type, payment_method, status, transaction_date FROM wbom_cash_transactions ORDER BY transaction_id DESC LIMIT 5"

echo ""
echo "=== LLM GATEWAY HEALTH CHECK ==="
docker exec fazle-wbom python3 -c "
import urllib.request, json
try:
    r = urllib.request.urlopen('http://fazle-llm-gateway:8800/health', timeout=5)
    print(json.loads(r.read().decode()))
except Exception as e:
    print(f'FAIL: {e}')
"

echo ""
echo "=== PROCESS-MESSAGE CORRECT FIELDS ==="
docker exec fazle-wbom python3 -c "
import urllib.request, json
data = json.dumps({
    'sender_number': '01958122300',
    'message_body': 'Rahim ke 500 taka diyechi bkash e',
    'whatsapp_msg_id': 'test-msg-audit-002'
}).encode()
req = urllib.request.Request(
    'http://localhost:9900/api/subagent/wbom/process-message',
    data=data,
    headers={
        'Content-Type': 'application/json',
        'X-Internal-Key': 'EDFEOdx968OTTlTpZnQzOL1359MEs-6HIV35F948pCA'
    }
)
try:
    r = urllib.request.urlopen(req, timeout=10)
    print(f'HTTP {r.status}')
    print(json.loads(r.read().decode()))
except urllib.error.HTTPError as e:
    print(f'HTTP {e.code}')
    print(e.read().decode()[:500])
except Exception as e:
    print(f'FAIL: {e}')
"

echo ""
echo "=== DONE ==="
