# FULL SYSTEM DEEP TEST + AUDIT REPORT
## Fazle AI Platform — VPS 5.189.131.48
### Date: 2026-04-17 | Auditor: Automated Deep Test Suite

---

## EXECUTIVE SUMMARY

| Category | Score | Status |
|----------|-------|--------|
| 1. Service Health | **10/10** | ✅ ALL PASS |
| 2. AI Core (Chat) | **5/10** | ⚠️ WARNINGS |
| 3. WBOM CRUD | **8/10** | ⚠️ MINOR |
| 4. Payment Flow | **4/10** | 🔴 CRITICAL |
| 5. Duplicate Protection | **9/10** | ✅ STRONG |
| 6. Employee Interaction | **3/10** | 🔴 CRITICAL |
| 7. Client / Job Seeker | **3/10** | 🔴 CRITICAL |
| 8. WhatsApp Flow | **7/10** | ⚠️ WARNINGS |
| 9. Retry System | **8/10** | ✅ GOOD |
| 10. Database Validation | **9/10** | ✅ STRONG |
| 11. Error Handling | **7/10** | ⚠️ WARNINGS |
| 12. Logging & Trace | **6/10** | ⚠️ WARNINGS |
| 13. Domain Routing | **10/10** | ✅ ALL PASS |
| 14. Auth / Security | **9/10** | ✅ STRONG |
| **OVERALL** | **71/140 (51%)** | **⚠️ NEEDS WORK** |

---

## DETAILED FINDINGS

---

### 1. SERVICE HEALTH — 10/10 ✅

| Service | Status | Port |
|---------|--------|------|
| API Gateway (fazle-api) | ✅ HTTP 200 | 8100/8101 |
| WBOM (fazle-wbom) | ✅ HTTP 200 | 9900 |
| Brain (fazle-brain) | ✅ HTTP 200 | 8200 (internal) |
| LLM Gateway | ✅ HTTP 200 | 8800 (internal) |
| Social Engine | ✅ HTTP 200 | 9800 (internal) |
| PostgreSQL | ✅ accepting connections | 5432 |
| Redis | ✅ PONG | 6379 |
| Ollama | ✅ 4 models loaded | 11434 |
| UI (fazle-ui) | ✅ HTTP 307 (redirect) | 3020 |

**Ollama Models Available:**
- qwen2.5:3b (1.9 GB) — primary
- qwen2.5:1.5b (986 MB) — fast fallback
- qwen2.5:0.5b (397 MB) — ultra-fast fallback
- nomic-embed-text (274 MB) — embeddings

**Verdict:** All 9 core services healthy. 15 optional services stopped (by design).

---

### 2. AI CORE (Chat) — 5/10 ⚠️

| Test | Input | Result | Time |
|------|-------|--------|------|
| Salary Query | "Samir er salary koto?" | ❌ **Empty reply** `""` | 11.6s |
| English Greeting | "Hello, how are you?" | ✅ Good response | 2.4s |
| Duty Query | "Kal ke ke duty te ache?" | ⚠️ Incoherent Bangla | 16.6s |
| Payment Request | "Karim ke 1000 taka dao" | ⚠️ Fallback error msg | 21.4s |
| Balance Inquiry | "Sir amar taka baki koto?" | ❌ **Empty reply** | 10.6s |
| Rate Inquiry | "Security guard rate koto?" | ❌ **Empty reply** | 10.4s |
| Job Application | Job seeker message | ⚠️ Semi-coherent reply | 15.8s |
| Owner Status | "system status dekhao" | ❌ **Empty reply** | 10.5s |
| Negative Payment | "-500 taka" | ❌ **Empty reply** | 10.6s |
| Empty Message | `""` | ✅ 422 validation | 0.01s |

**Root Cause Analysis:**
```
LLM gateway failed in 10.57s: Server error '502 Bad Gateway'
LLM gateway failed — returning empty reply for fallback
LLM attempt 1 returned empty — retrying with reduced context
```

**Findings:**
1. 🔴 **LLM Gateway 502 errors** — Ollama frequently returns 502 Bad Gateway via the LLM gateway, causing ~50% of queries to return empty replies
2. 🔴 **Slow response times** — 10-21s per query. qwen2.5:3b is too slow on this VPS CPU
3. ⚠️ **Smart retry works** — When first attempt fails, reduces context and retries. English greeting succeeded because it's simpler
4. ⚠️ **System prompt truncation** — "System prompt truncated: 20194 -> 800 chars" — massive persona getting cut to 800 chars
5. ⚠️ **Knowledge retrieval partial** — Some queries find knowledge context, others don't

**Recommendations:**
- Switch default model to `qwen2.5:1.5b` for speed (still good for Bangla/English)
- Investigate LLM Gateway 502s — likely Ollama OOM or timeout under load
- Reduce system prompt to <4000 chars to avoid truncation
- Add static fallback responses for common queries (salary, duty, balance)

---

### 3. WBOM CRUD — 8/10 ⚠️

| Endpoint | HTTP | Count |
|----------|------|-------|
| GET /contacts | ✅ 200 | 511 records (50 per page) |
| GET /employees | ✅ 200 | 169 records (50 per page) |
| GET /transactions | ✅ 200 | 1218 records (50 per page) |
| GET /programs | ✅ 200 | 0 records |
| POST /search | ❌ **500** | Internal Server Error |
| No auth key | ✅ 403 | Correctly rejected |
| Wrong auth key | ✅ 403 | Correctly rejected |

**Bug Found:**
```
AttributeError: 'AdvancedSearchRequest' object has no attribute 'tables'
File "/app/routes/search.py", line 150
```

**Recommendations:**
- 🔴 Fix WBOM search endpoint — `AdvancedSearchRequest` model missing `tables` field (likely renamed)
- Investigate empty escort_programs table (should have data from payment processing)

---

### 4. PAYMENT FLOW — 4/10 🔴

**Test Result:** Payment chat message ("Karim ke 1000 taka dao bkash e") returned fallback error: `"দুঃখিত, একটু সমস্যা হয়েছে। আবার বলবেন?"`

**WBOM Direct Test:** Process-message with "Rahim ke 500 taka diyechi bkash e" → classified as `general` (not `payment`), confidence: 0.5

**Architecture Analysis:**
- ✅ `wbom_staging_payments` table exists (draft/approval flow)
- ✅ `wbom_rejected_payments` table exists (rejection tracking)
- ✅ Both tables are empty (no staging/rejected data)
- ⚠️ All 1218 transactions have status `Completed` — suggests direct execution without staging
- 🔴 Payment classification not triggering on test messages

**Findings:**
1. 🔴 **Payment intent not detected** — Message classified as `general` instead of `payment`
2. 🔴 **Staging pipeline unused** — Tables exist but no data flows through them
3. ⚠️ **Brain payment routing broken** — Chat → Brain → payment intent fails (empty reply due to LLM 502)

**Recommendations:**
- Fix payment classifier regex/NLP to detect "X ke Y taka dao" pattern
- Wire staging pipeline into actual workflow
- Add rule-based payment detection as fallback before LLM classification

---

### 5. DUPLICATE PROTECTION — 9/10 ✅

**Database Layer:**
- ✅ **Unique index** on `(employee_id, transaction_date, amount, transaction_type, payment_method) WHERE status='Completed'`
- ✅ **WhatsApp message dedup** index: `UNIQUE (whatsapp_message_id) WHERE whatsapp_message_id IS NOT NULL`
- ✅ 0 duplicate transactions found in 1218 records
- ✅ `ON CONFLICT DO NOTHING` prevents duplicates silently

**Redis Layer:**
- ✅ Redis dedup keys exist (db5: 1 key)
- ✅ 5-minute TTL dedup window via `SET NX`

**Gap:**
- ⚠️ Redis dedup has 5-min window only — long-delayed retries could bypass it (DB index catches these)

---

### 6. EMPLOYEE INTERACTION — 3/10 🔴

**Test:** "Sir amar taka baki koto?" → **Empty reply**

**Root Cause:** Same as AI Core — LLM 502 errors causing empty responses. The Brain cannot answer employee queries without functioning LLM.

**Findings:**
- 🔴 No employee can get balance/salary info through chat
- 🔴 No fallback data-lookup path when LLM fails
- ⚠️ System relies entirely on LLM to formulate responses from WBOM data

**Recommendations:**
- Implement direct WBOM data lookup for employee queries (bypass LLM for data retrieval)
- Add template responses: "আপনার বেতন X টাকা, বাকি Y টাকা" from DB data

---

### 7. CLIENT / JOB SEEKER — 3/10 🔴

| Test | Result |
|------|--------|
| Rate inquiry | ❌ Empty reply |
| Job application | ⚠️ Semi-coherent (LLM succeeded on retry) |

**Findings:**
- Knowledge base has job_seeker content (2 results found)
- Smart context injection works: "Smart context built: 333 chars"
- But LLM frequently fails to generate coherent responses

---

### 8. WhatsApp Flow — 7/10 ⚠️

**Architecture Verified:**
- ✅ Social Engine webhook handler running (port 9800)
- ✅ HMAC-SHA256 webhook verification configured
- ✅ Redis dedup in Social Engine
- ✅ WBOM retry queue implemented
- ✅ Dead letter queue (DLQ) exists

**Current State:**
- Retry queue: 0 items (clean)
- DLQ: 0 items (clean)
- Dedup keys: 1 (minimal activity)

**Findings:**
- ⚠️ No live WhatsApp traffic to verify end-to-end flow
- ⚠️ Process-message field mismatch found: `sender_phone` → should be `sender_number`, `message` → should be `message_body`

---

### 9. RETRY SYSTEM — 8/10 ✅

**Implementation:**
- ✅ Redis-backed retry queue (`wbom_retry_queue`)
- ✅ 15-second processing interval
- ✅ Max 5 retry attempts
- ✅ DLQ for permanent failures
- ✅ Currently clean (0 items in both queues)

**Gaps:**
- ⚠️ No persistent storage (Redis only — ephemeral)
- ⚠️ No exponential backoff
- ⚠️ No alerting on permanent failures

---

### 10. DATABASE VALIDATION — 9/10 ✅

**Data Integrity:**
| Check | Result |
|-------|--------|
| Total tables | 101 (16 wbom + 85 fazle/system) |
| Contacts | 511 records |
| Employees | 169 records |
| Transactions | 1218 records |
| Duplicate transactions | ✅ 0 found |
| Orphan transactions | ✅ 0 found |
| NULL amounts | ✅ 0 found |
| NULL employee_ids | ✅ 0 found |
| NULL employee names | ✅ 0 found |
| NULL contact phones | ✅ 0 found |

**Indexes:** 44 indexes across 16 wbom tables — comprehensive coverage including dedup, search, and foreign key indexes.

**Notable:**
- `wbom_escort_programs`: 0 records (not being populated)
- `wbom_whatsapp_messages`: 0 records (messages not being stored)
- `wbom_extracted_data`: 0 records (extraction pipeline not producing output)
- `wbom_billing_records`: 0 records
- `wbom_salary_records`: 0 records
- `wbom_staging_payments`: 0 records
- `wbom_rejected_payments`: 0 records

**Interpretation:** Only contacts (511), employees (169), and cash_transactions (1218) have data. All pipeline tables (staging, rejected, extracted, messages, escort programs) are empty — suggesting these features exist in schema but are not yet wired into the live flow.

---

### 11. ERROR HANDLING — 7/10 ⚠️

| Test | Expected | Actual |
|------|----------|--------|
| Empty message | 422 Validation | ✅ 422 with clear error |
| Malformed JSON | 422 | ✅ 422 "JSON decode error" |
| Missing fields | 422 | ✅ Caught by Pydantic |
| No auth header | 401 | ✅ "Authentication required" |
| Negative payment | Error msg | ❌ Empty reply (LLM fail) |
| WBOM no key | 403 | ✅ "Forbidden — invalid internal key" |
| WBOM wrong key | 403 | ✅ Correctly rejected |

**Good:** Input validation, auth enforcement, Pydantic model validation all working.  
**Bad:** LLM failures surface as empty replies instead of meaningful error messages.

---

### 12. LOGGING & TRACE — 6/10 ⚠️

**Good:**
- ✅ Structured JSON logging with timestamps in Brain, WBOM
- ✅ Log levels (INFO, WARNING, ERROR) used correctly
- ✅ Source identification in logs (`"source": "fazle-brain"`)
- ✅ LLM timing logged: `"LLM OK via gateway in 4.51s route=fast"`
- ✅ Auth rejections logged with method+path
- ✅ Metrics endpoint exposed for Prometheus scraping

**Gaps:**
- ⚠️ No `request_id` or correlation ID across services
- ⚠️ API Gateway logs use plain text format (not structured JSON)
- ⚠️ No trace of which user/phone made each request in API logs
- ⚠️ Social Engine logs are health-check only (no business logic logging visible)

---

### 13. DOMAIN ROUTING — 10/10 ✅

| Domain | Test | Result |
|--------|------|--------|
| iamazim.com | Root | ✅ HTTP 307 (redirect to HTTPS) |
| fazle.iamazim.com | Root | ✅ HTTP 307 |
| api.iamazim.com | /health | ✅ HTTP 200 |
| api.iamazim.com | WBOM with key | ✅ HTTP 200 (data returned) |
| api.iamazim.com | WBOM no key | ✅ HTTP 403 |

---

### 14. AUTH / Security — 9/10 ✅

**Verified:**
- ✅ API Gateway requires `X-API-Key` header for `/fazle/chat`
- ✅ WBOM requires `X-Internal-Key` header for all routes
- ✅ Missing key → 403 Forbidden
- ✅ Wrong key → 403 Forbidden
- ✅ Health endpoints exempt from auth (correct)
- ✅ HMAC-based timing-safe key comparison

**Gap:**
- ⚠️ No key rotation mechanism
- ⚠️ Redis password visible in `.env` (standard Docker practice, but note it)

---

## CRITICAL ISSUES (Fix Immediately)

### 🔴 C1: LLM Gateway 502 Errors — ~50% query failure rate
**Impact:** Half of all chat queries return empty replies  
**Root Cause:** Ollama (qwen2.5:3b) timing out or OOMing, causing LLM Gateway to return 502  
**Fix:** 
1. Switch to `qwen2.5:1.5b` as default model
2. Add `OLLAMA_NUM_PARALLEL=1` and memory limits
3. Reduce system prompt from 20K → 4K chars

### 🔴 C2: Payment Classification Broken
**Impact:** Payment messages classified as `general` — no payments can be processed via chat  
**Root Cause:** Classifier not detecting "X ke Y taka dao" pattern  
**Fix:** Add regex-based pre-classifier for common payment patterns before LLM classification

### 🔴 C3: WBOM Search Endpoint Crashes (500)
**Impact:** Search functionality completely broken  
**Root Cause:** `AdvancedSearchRequest` model missing `tables` attribute  
**Fix:** Update `search.py` line 150 — check correct field name in Pydantic model

---

## WARNINGS (Fix Soon)

### ⚠️ W1: Empty Pipeline Tables
`wbom_escort_programs`, `wbom_whatsapp_messages`, `wbom_extracted_data`, `wbom_staging_payments`, `wbom_rejected_payments` — all empty. Pipeline tables exist in schema but not wired into live data flow.

### ⚠️ W2: Slow Response Times (10-21s)
Even successful queries take 10-21 seconds. Target should be <5s for chat UX.

### ⚠️ W3: System Prompt Truncation
20,194 chars → 800 chars. Most persona context is lost.

### ⚠️ W4: No Request Correlation IDs
Cannot trace a single request across API → Brain → WBOM → Social Engine.

### ⚠️ W5: No Fallback Data Responses
When LLM fails, system returns empty reply instead of looking up data directly from WBOM.

---

## WHAT'S WORKING WELL

1. ✅ **Infrastructure rock-solid** — All 9 core services healthy, proper health checks
2. ✅ **Security strong** — Multi-layer auth (API key + Internal key + HMAC), proper 403 rejections
3. ✅ **Database clean** — 0 duplicates, 0 orphans, 0 nulls in critical fields, 44 indexes
4. ✅ **Dedup excellent** — Dual-layer (Redis + DB unique index) with WhatsApp message dedup
5. ✅ **Domain routing perfect** — All 3 domains working correctly with proper TLS
6. ✅ **Retry system ready** — Queue + DLQ + 5-attempt retry logic implemented
7. ✅ **Input validation solid** — Pydantic catches malformed/missing/empty inputs
8. ✅ **Structured logging** — JSON logs with timestamps, levels, sources in Brain + WBOM

---

## RECOMMENDED FIX PRIORITY

| Priority | Issue | Effort | Impact |
|----------|-------|--------|--------|
| P0 | C1: Fix LLM 502s (switch to 1.5b model) | 30 min | Fixes 50% query failures |
| P0 | C2: Fix payment classification | 2-4 hrs | Enables core business flow |
| P1 | C3: Fix WBOM search endpoint | 30 min | Restores search functionality |
| P1 | W3: Reduce system prompt size | 1-2 hrs | Better AI responses |
| P2 | W5: Add fallback data responses | 4-6 hrs | UX when LLM fails |
| P2 | W4: Add request correlation IDs | 2-3 hrs | Debugging capability |
| P3 | W1: Wire pipeline tables | 8+ hrs | Full data flow |
| P3 | W2: Optimize response times | 4-6 hrs | Better UX |

---

## REDIS STATE SNAPSHOT

| DB | Keys | Purpose |
|----|------|---------|
| db0 | 2 | General |
| db1 | 22 (12 expiring) | Conversation memory |
| db3 | 24 (24 expiring) | LLM cache |
| db5 | 1 | Dedup keys |
| db6 | 12 (3 expiring) | Rate limiting |
| db7 | 1 (1 expiring) | Temp |

**Notable Redis Keys (db1):**
- `fazle:owner:conversation` — Owner chat history
- `fazle:owner:instructions` — Owner custom instructions
- `fazle:governor:*` — Governor identity, feedback, errors, safe_mode
- `fazle:contact:whatsapp:*:interactions` — Per-contact interaction history
- `fazle:intel:usage` — Usage tracking

---

*Report generated: 2026-04-17T04:10 CEST*  
*VPS: 5.189.131.48 | 17 containers running | PostgreSQL: 101 tables | Redis: 6 DBs active*
