import urllib.request, json

# Test 1: /fazle/admin/login with wrong creds
data = json.dumps({"username": "test@test.com", "password": "wrong"}).encode()
req = urllib.request.Request("http://127.0.0.1:8100/fazle/admin/login", data=data, headers={"Content-Type": "application/json"})
try:
    resp = urllib.request.urlopen(req)
    print("TEST1:", resp.status, resp.read().decode())
except urllib.error.HTTPError as e:
    print("TEST1:", e.code, e.read().decode())

# Test 2: /fazle/admin/login via nginx proxy path
data2 = json.dumps({"username": "test@test.com", "password": "wrong"}).encode()
req2 = urllib.request.Request("http://127.0.0.1:3020/api/fazle/admin/login", data=data2, headers={"Content-Type": "application/json"})
try:
    resp2 = urllib.request.urlopen(req2)
    print("TEST2:", resp2.status, resp2.read().decode())
except urllib.error.HTTPError as e:
    print("TEST2:", e.code, e.read().decode())
