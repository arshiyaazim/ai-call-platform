import httpx, json, os

key = os.environ.get("OPENAI_API_KEY", "")
print(f"Key: {len(key)} chars, starts: {key[:25]}...")

# Test 1: Embedding with text-embedding-3-large
print("\n--- Test 1: text-embedding-3-large ---")
try:
    r = httpx.post(
        "https://api.openai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": "text-embedding-3-large", "input": "test vision activation"},
        timeout=15
    )
    if r.status_code == 200:
        dims = len(r.json()["data"][0]["embedding"])
        print(f"OK — {dims} dimensions")
    else:
        print(f"FAIL — {r.status_code}: {r.text[:200]}")
except Exception as e:
    print(f"ERROR: {e}")

# Test 2: search-multimodal endpoint
print("\n--- Test 2: search-multimodal endpoint ---")
try:
    r = httpx.post(
        "http://localhost:8300/search-multimodal",
        json={"query": "test photo", "user_id": "test", "limit": 1},
        timeout=15
    )
    print(f"Status: {r.status_code}")
    print(f"Body: {r.text[:300]}")
except Exception as e:
    print(f"ERROR: {e}")

# Test 3: search-all endpoint
print("\n--- Test 3: search-all endpoint ---")
try:
    r = httpx.post(
        "http://localhost:8300/search-all",
        json={"query": "test multimodal", "user_id": "test", "limit": 1},
        timeout=15
    )
    print(f"Status: {r.status_code}")
    print(f"Body: {r.text[:300]}")
except Exception as e:
    print(f"ERROR: {e}")
