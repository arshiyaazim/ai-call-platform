import urllib.request, json

# Test via nginx proxy (same path the UI calls)
data = json.dumps({"username": "azim@iamazim.com", "password": "wrong"}).encode()
req = urllib.request.Request("https://fazle.iamazim.com/api/fazle/admin/login", data=data, headers={"Content-Type": "application/json"})
try:
    resp = urllib.request.urlopen(req)
    print("NGINX_TEST:", resp.status, resp.read().decode())
except urllib.error.HTTPError as e:
    print("NGINX_TEST:", e.code, e.read().decode())
except Exception as e:
    print("NGINX_TEST ERROR:", str(e))

# Test direct API (bypass nginx)
data2 = json.dumps({"username": "azim@iamazim.com", "password": "wrong"}).encode()
req2 = urllib.request.Request("http://127.0.0.1:8100/fazle/admin/login", data=data2, headers={"Content-Type": "application/json"})
try:
    resp2 = urllib.request.urlopen(req2)
    print("DIRECT_TEST:", resp2.status, resp2.read().decode())
except urllib.error.HTTPError as e:
    print("DIRECT_TEST:", e.code, e.read().decode())
