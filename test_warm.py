import urllib.request, json, time

data = json.dumps({"user_id": "test123", "message": "What are the latest business reports from WBOM? Give me a summary.", "source": "whatsapp"}).encode()
req = urllib.request.Request("http://localhost:8200/chat", data=data, headers={"Content-Type": "application/json"}, method="POST")
t0 = time.time()
try:
    resp = urllib.request.urlopen(req, timeout=45)
    elapsed = time.time() - t0
    result = json.loads(resp.read().decode())
    print(f"Time: {elapsed:.1f}s")
    print(f"Route: {result.get('route', 'N/A')}")
    print(f"Reply: {result.get('reply', '')[:200]}")
except Exception as e:
    print(f"Time: {time.time()-t0:.1f}s ERROR: {e}")
