import urllib.request, json, time

def test_chat(label, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request("http://localhost:8200/chat", data=data, headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=40)
        elapsed = time.time() - t0
        result = json.loads(resp.read().decode())
        print(f"\n=== {label} ({elapsed:.1f}s) ===")
        print(f"  route:  {result.get('route', 'N/A')}")
        print(f"  reply:  {result.get('reply', '')[:120]}")
    except Exception as e:
        elapsed = time.time() - t0
        print(f"\n=== {label} ({elapsed:.1f}s) === ERROR: {e}")

# Test 1: Simple self → should take fast path
test_chat("simple-self", {"user_id": "test123", "message": "hi", "source": "whatsapp"})

# Test 2: Complex self → should go through full pipeline with route
test_chat("complex-self", {"user_id": "test123", "message": "What are the latest business reports from WBOM? Give me a summary of recent transactions.", "source": "whatsapp"})

# Test 3: Social relationship → full pipeline
test_chat("social-basic", {"user_id": "social_test", "message": "Hello, I want to know about your services", "relationship": "social", "conversation_id": "social-whatsapp-01712345678", "source": "whatsapp"})

# Test 4: Social Bangla → full pipeline
test_chat("social-bangla", {"user_id": "social_test2", "message": "আপনাদের সার্ভিস সম্পর্কে জানতে চাই", "relationship": "social", "conversation_id": "social-whatsapp-01798765432", "source": "whatsapp"})
