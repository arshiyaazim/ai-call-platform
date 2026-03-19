import httpx, time, json

BRAIN_URL = "http://fazle-brain:8200"

print("=== Pre-warm: 2 raw Ollama hits ===")
with httpx.Client(timeout=30.0) as client:
    for i in range(2):
        t0 = time.monotonic()
        resp = client.post("http://ollama:11434/api/generate",
                           json={"model": "qwen2.5:0.5b", "prompt": "hi",
                                 "system": "Reply briefly.", "stream": False,
                                 "options": {"num_predict": 5, "num_ctx": 512}})
        print(f"  Warm {i+1}: {(time.monotonic()-t0)*1000:.0f}ms")
        time.sleep(2)

print()
print("=== /chat/fast Endpoint (10s gaps, simple prompts) ===")
with httpx.Client(timeout=60.0) as client:
    for i in range(5):
        time.sleep(10)  # 10 second gap
        t0 = time.monotonic()
        ttfb = None
        tokens = []
        
        with client.stream("POST", f"{BRAIN_URL}/chat/fast",
                          json={"message": "hi", "source": "bench"}) as resp:
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    if ttfb is None:
                        ttfb = (time.monotonic() - t0) * 1000
                    try:
                        chunk = json.loads(line[6:])
                        tokens.append(chunk.get("content", ""))
                    except:
                        pass
        
        total = (time.monotonic() - t0) * 1000
        reply = "".join(tokens)
        print(f"Run {i+1}: TTFB={ttfb:.0f}ms Total={total:.0f}ms Tokens={len(tokens)} Reply={repr(reply[:50])}")
