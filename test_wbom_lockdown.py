#!/usr/bin/env python3
import urllib.request, json

print("=== 1. No auth (expect 401) ===")
try:
    r = urllib.request.urlopen("http://localhost:8100/fazle/wbom/employees?limit=1")
    print(f"FAIL - got {r.status}")
except urllib.error.HTTPError as e:
    print(f"OK - {e.code} {json.loads(e.read())}")

print("\n=== 2. Login ===")
data = json.dumps({"username": "azim@iamazim.com", "password": "Jilapi.1234"}).encode()
req = urllib.request.Request("http://localhost:8100/fazle/admin/login", data=data,
                             headers={"Content-Type": "application/json"}, method="POST")
resp = json.loads(urllib.request.urlopen(req).read())
token = resp.get("token", "")
print(f"TOKEN: {token[:20]}..." if token else "TOKEN: FAIL")

print("\n=== 3. With auth (expect 200 + data) ===")
req2 = urllib.request.Request("http://localhost:8100/fazle/wbom/employees?limit=2",
                              headers={"Authorization": f"Bearer {token}"})
r2 = urllib.request.urlopen(req2)
result = json.loads(r2.read())
print(f"OK - {r2.status} - {len(result)} employees returned")
if result:
    print(f"  First: {result[0].get('employee_name', 'N/A')}")
