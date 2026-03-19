import httpx
r = httpx.get("http://localhost:8200/health")
print(r.status_code, r.text)
