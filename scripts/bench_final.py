import httpx, time, json

BRAIN_URL = "http://fazle-brain:8200"
PROMPTS = ["hey", "how are you", "what time is it", "tell me a joke", "good morning"]

print("=== /chat/fast Endpoint Benchmark ===")
print(f"Target: fazle-brain:8200/chat/fast")
print()

with httpx.Client(timeout=30.0) as client:
    for i, prompt in enumerate(PROMPTS):
        time.sleep(5)  # 5 second gap between requests
        t0 = time.monotonic()
        ttfb = None
        tokens = []
        
        with client.stream("POST", f"{BRAIN_URL}/chat/fast",
                          json={"message": prompt, "source": "bench"}) as resp:
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
        print(f"Run {i+1}: TTFB={ttfb:.0f}ms Total={total:.0f}ms Tokens={len(tokens)} Reply={repr(reply[:60])}")

print()
print("=== Raw Ollama Benchmark (comparison) ===")
with httpx.Client(timeout=30.0) as client:
    for i in range(3):
        time.sleep(3)
        t0 = time.monotonic()
        ttfb = None
        tokens = 0
        with client.stream("POST", "http://ollama:11434/api/generate",
                          json={"model": "qwen2.5:0.5b", "prompt": "hi",
                                "system": "Reply in one sentence.",
                                "stream": True,
                                "options": {"num_predict": 10, "num_ctx": 512}}) as resp:
            for line in resp.iter_lines():
                if line.strip():
                    if ttfb is None:
                        ttfb = (time.monotonic() - t0) * 1000
                    try:
                        d = json.loads(line)
                        if not d.get("done"):
                            tokens += 1
                    except:
                        pass
        total = (time.monotonic() - t0) * 1000
        print(f"Raw {i+1}: TTFB={ttfb:.0f}ms Total={total:.0f}ms Tokens={tokens}")
