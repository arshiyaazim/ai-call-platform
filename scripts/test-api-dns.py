import httpx

# Test DNS resolution of fazle-api from brain
try:
    r = httpx.get("http://fazle-api:8100/health", timeout=5)
    print("fazle-api:8100 ->", r.status_code, r.text)
except Exception as e:
    print("fazle-api:8100 FAIL:", e)

# Test DNS resolution of fazle-api-blue from brain  
try:
    r = httpx.get("http://fazle-api-blue:8100/health", timeout=5)
    print("fazle-api-blue:8100 ->", r.status_code, r.text)
except Exception as e:
    print("fazle-api-blue:8100 FAIL:", e)
