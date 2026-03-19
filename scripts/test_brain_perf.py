#!/usr/bin/env python3
"""Test Fazle Brain chat endpoint performance."""
import urllib.request
import json
import time

BRAIN_URL = "http://localhost:8200"

def test_chat():
    """Test /chat endpoint latency."""
    payload = json.dumps({
        "message": "Hey bro what is up?",
        "user": "Azim",
        "relationship": "self"
    }).encode()
    
    req = urllib.request.Request(
        f"{BRAIN_URL}/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    start = time.time()
    resp = urllib.request.urlopen(req, timeout=60)
    body = resp.read().decode()
    elapsed = time.time() - start
    
    data = json.loads(body)
    print(f"Reply: {data.get('reply', 'N/A')[:200]}")
    print(f"Chat latency: {elapsed:.2f}s")
    return elapsed

def test_stream():
    """Test /chat/stream SSE endpoint latency (TTFB)."""
    payload = json.dumps({
        "message": "Tell me something interesting",
        "user": "Azim",
        "relationship": "self",
        "source": "voice"
    }).encode()
    
    req = urllib.request.Request(
        f"{BRAIN_URL}/chat/stream",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    start = time.time()
    resp = urllib.request.urlopen(req, timeout=60)
    first_byte = None
    chunks = []
    
    for line in resp:
        line = line.decode().strip()
        if line.startswith("data: "):
            if first_byte is None:
                first_byte = time.time() - start
            chunk_data = json.loads(line[6:])
            content = chunk_data.get("content", "")
            if content:
                chunks.append(content)
            if chunk_data.get("done"):
                break
    
    total = time.time() - start
    full_text = "".join(chunks)
    print(f"\nStream reply: {full_text[:200]}")
    print(f"Stream TTFB: {first_byte:.2f}s" if first_byte else "No chunks received")
    print(f"Stream total: {total:.2f}s")
    return first_byte, total

def test_health():
    """Test /health endpoint."""
    req = urllib.request.Request(f"{BRAIN_URL}/health")
    resp = urllib.request.urlopen(req, timeout=5)
    data = json.loads(resp.read().decode())
    print(f"Health: {data}")

if __name__ == "__main__":
    print("=== Fazle Brain Performance Test ===\n")
    
    print("1. Health check...")
    try:
        test_health()
    except Exception as e:
        print(f"Health check failed: {e}")
        exit(1)
    
    print("\n2. Chat endpoint test...")
    try:
        chat_time = test_chat()
    except Exception as e:
        print(f"Chat test failed: {e}")
        chat_time = None
    
    print("\n3. Streaming endpoint test...")
    try:
        stream_ttfb, stream_total = test_stream()
    except Exception as e:
        print(f"Stream test failed: {e}")
        stream_ttfb = stream_total = None
    
    print("\n=== Summary ===")
    if chat_time:
        print(f"Chat: {chat_time:.2f}s {'OK' if chat_time < 5 else 'SLOW'}")
    if stream_ttfb:
        print(f"Stream TTFB: {stream_ttfb:.2f}s {'OK' if stream_ttfb < 3 else 'SLOW'}")
        print(f"Stream Total: {stream_total:.2f}s {'OK' if stream_total < 5 else 'SLOW'}")
