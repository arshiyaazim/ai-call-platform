import httpx, time, sys

url = "http://localhost:8200/chat/fast"
payload = {"message": "hi", "source": "voice"}

# Warm up
for i in range(2):
    r = httpx.post(url, json=payload, timeout=60)
    sys.stdout.write(f"Warmup {i+1}: {r.status_code}\n")
    sys.stdout.flush()

sys.stdout.write("\n")
sys.stdout.flush()

# Benchmark 10 sequential runs
results = []
for i in range(10):
    start = time.monotonic()
    try:
        with httpx.stream("POST", url, json=payload, timeout=60) as r:
            for line in r.iter_lines():
                if line.startswith("data: "):
                    ttfb = (time.monotonic() - start) * 1000
                    results.append(ttfb)
                    sys.stdout.write(f"Run {i+1}: {ttfb:.0f}ms\n")
                    sys.stdout.flush()
                    break
    except Exception as e:
        sys.stdout.write(f"Run {i+1}: ERROR {e}\n")
        sys.stdout.flush()

if results:
    sys.stdout.write(f"\nMin: {min(results):.0f}ms  Avg: {sum(results)/len(results):.0f}ms  Max: {max(results):.0f}ms  P50: {sorted(results)[len(results)//2]:.0f}ms\n")
    sys.stdout.flush()
