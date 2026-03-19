#!/usr/bin/env python3
"""Benchmark Ollama raw TTFB and Brain fast-path TTFB."""
import urllib.request
import json
import time
import sys

OLLAMA_URL = "http://172.22.0.2:11434"
BRAIN_URL = "http://172.22.0.4:8200"


def bench_ollama_raw():
    """Direct Ollama streaming TTFB — the absolute floor."""
    payload = json.dumps({
        "model": "qwen2.5:3b",
        "messages": [
            {"role": "system", "content": "You are Azim. Reply in 1-2 short sentences. Plain text only."},
            {"role": "user", "content": "Hey bro what is up?"}
        ],
        "stream": True
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    start = time.time()
    resp = urllib.request.urlopen(req, timeout=30)
    first_token_time = None
    tokens = []
    for line in resp:
        line = line.decode().strip()
        if not line:
            continue
        data = json.loads(line)
        content = data.get("message", {}).get("content", "")
        if content and first_token_time is None:
            first_token_time = time.time() - start
        if content:
            tokens.append(content)
        if data.get("done"):
            break
    total = time.time() - start
    text = "".join(tokens)
    print(f"  TTFB:  {first_token_time*1000:.0f} ms")
    print(f"  Total: {total*1000:.0f} ms")
    print(f"  Reply: {text[:120]}")
    return first_token_time


def bench_brain_stream():
    """Brain /chat/stream endpoint TTFB."""
    payload = json.dumps({
        "message": "Hey bro what is up?",
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
    first_token_time = None
    tokens = []
    for line in resp:
        line = line.decode().strip()
        if not line or not line.startswith("data: "):
            continue
        chunk_str = line[6:].strip()
        if not chunk_str:
            continue
        try:
            chunk = json.loads(chunk_str)
            content = chunk.get("content", "")
            done = chunk.get("done", False)
            if content and first_token_time is None:
                first_token_time = time.time() - start
            if content:
                tokens.append(content)
            if done:
                break
        except json.JSONDecodeError:
            continue
    total = time.time() - start
    text = "".join(tokens)
    print(f"  TTFB:  {first_token_time*1000:.0f} ms" if first_token_time else "  TTFB:  N/A")
    print(f"  Total: {total*1000:.0f} ms")
    print(f"  Reply: {text[:120]}")
    return first_token_time


def bench_brain_fast():
    """Brain /chat/fast endpoint TTFB (if available)."""
    payload = json.dumps({
        "message": "Hey bro what is up?",
        "user": "Azim",
        "relationship": "self",
        "source": "voice"
    }).encode()
    req = urllib.request.Request(
        f"{BRAIN_URL}/chat/fast",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        start = time.time()
        resp = urllib.request.urlopen(req, timeout=30)
        first_token_time = None
        tokens = []
        for line in resp:
            line = line.decode().strip()
            if not line or not line.startswith("data: "):
                continue
            chunk_str = line[6:].strip()
            if not chunk_str:
                continue
            try:
                chunk = json.loads(chunk_str)
                content = chunk.get("content", "")
                done = chunk.get("done", False)
                if content and first_token_time is None:
                    first_token_time = time.time() - start
                if content:
                    tokens.append(content)
                if done:
                    break
            except json.JSONDecodeError:
                continue
        total = time.time() - start
        text = "".join(tokens)
        print(f"  TTFB:  {first_token_time*1000:.0f} ms" if first_token_time else "  TTFB:  N/A")
        print(f"  Total: {total*1000:.0f} ms")
        print(f"  Reply: {text[:120]}")
        return first_token_time
    except Exception as e:
        print(f"  Not available: {e}")
        return None


if __name__ == "__main__":
    print("=" * 50)
    print("FAZLE AI LATENCY BENCHMARK")
    print("=" * 50)

    print("\n1. Raw Ollama TTFB (baseline floor):")
    ollama_ttfb = bench_ollama_raw()

    print("\n2. Brain /chat/stream TTFB (current):")
    stream_ttfb = bench_brain_stream()

    print("\n3. Brain /chat/fast TTFB (ultra-fast path):")
    fast_ttfb = bench_brain_fast()

    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    if ollama_ttfb:
        print(f"  Ollama raw:     {ollama_ttfb*1000:>6.0f} ms")
    if stream_ttfb:
        print(f"  Brain stream:   {stream_ttfb*1000:>6.0f} ms")
    if fast_ttfb:
        print(f"  Brain fast:     {fast_ttfb*1000:>6.0f} ms")
        overhead = (fast_ttfb - ollama_ttfb) * 1000 if ollama_ttfb else 0
        print(f"  Fast overhead:  {overhead:>6.0f} ms (over raw Ollama)")
    print(f"\n  Target: < 500 ms TTFB")
