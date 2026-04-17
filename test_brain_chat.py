import urllib.request, json
data = json.dumps({"user_id": "test123", "message": "hi", "source": "whatsapp"}).encode()
req = urllib.request.Request("http://localhost:8200/chat", data=data, headers={"Content-Type": "application/json"}, method="POST")
try:
    resp = urllib.request.urlopen(req, timeout=35)
    print(resp.read().decode()[:500])
except Exception as e:
    print(f"ERROR: {e}")
