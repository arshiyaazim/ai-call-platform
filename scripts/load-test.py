#!/usr/bin/env python3
"""
Fazle Load Test — Simulate 50 concurrent users hitting the LLM system.

Usage:
    python load-test.py [--gateway URL] [--queue URL] [--users N] [--rounds N]

Requires: pip install httpx
"""
import asyncio
import argparse
import httpx
import time
import json
import statistics
from dataclasses import dataclass, field


@dataclass
class Stats:
    latencies: list[float] = field(default_factory=list)
    errors: int = 0
    cache_hits: int = 0
    rate_limited: int = 0
    success: int = 0

    def summary(self, label: str) -> str:
        total = self.success + self.errors + self.rate_limited
        if not self.latencies:
            return f"[{label}] {total} requests, {self.errors} errors, {self.rate_limited} rate-limited — no successful latencies"
        p50 = statistics.median(self.latencies)
        p95 = self.latencies[int(len(self.latencies) * 0.95)] if len(self.latencies) > 1 else p50
        p99 = self.latencies[int(len(self.latencies) * 0.99)] if len(self.latencies) > 1 else p50
        avg = statistics.mean(self.latencies)
        self.latencies.sort()
        return (
            f"[{label}]\n"
            f"  Total: {total} | Success: {self.success} | Errors: {self.errors} | Rate-limited: {self.rate_limited}\n"
            f"  Cache hits: {self.cache_hits}\n"
            f"  Latency — avg: {avg:.0f}ms | p50: {p50:.0f}ms | p95: {p95:.0f}ms | p99: {p99:.0f}ms\n"
            f"  Min: {min(self.latencies):.0f}ms | Max: {max(self.latencies):.0f}ms"
        )


PROMPTS = [
    [{"role": "user", "content": "What is the capital of France?"}],
    [{"role": "user", "content": "Explain quantum computing in one sentence."}],
    [{"role": "user", "content": "Write a haiku about programming."}],
    [{"role": "user", "content": "What is 2+2?"}],
    [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": "Hello!"}],
    [{"role": "user", "content": "Name three colors."}],
    [{"role": "user", "content": "What day comes after Monday?"}],
    [{"role": "user", "content": "Translate 'hello' to Spanish."}],
]


async def test_gateway_sync(client: httpx.AsyncClient, gateway_url: str, user_id: int, prompt_idx: int, stats: Stats):
    """Send a synchronous request to the LLM Gateway."""
    messages = PROMPTS[prompt_idx % len(PROMPTS)]
    payload = {
        "messages": messages,
        "caller": f"loadtest-user-{user_id}",
        "user_id": f"user-{user_id}",
        "cache": True,
        "stream": False,
        "temperature": 0.1,
    }
    start = time.monotonic()
    try:
        resp = await client.post(f"{gateway_url}/generate", json=payload)
        latency_ms = (time.monotonic() - start) * 1000
        if resp.status_code == 200:
            data = resp.json()
            stats.success += 1
            stats.latencies.append(latency_ms)
            if data.get("cached"):
                stats.cache_hits += 1
        elif resp.status_code == 429:
            stats.rate_limited += 1
        else:
            stats.errors += 1
    except Exception:
        stats.errors += 1


async def test_queue_async(client: httpx.AsyncClient, queue_url: str, user_id: int, prompt_idx: int, stats: Stats):
    """Enqueue a request and poll for result."""
    messages = PROMPTS[prompt_idx % len(PROMPTS)]
    payload = {
        "messages": messages,
        "caller": f"loadtest-user-{user_id}",
        "cache": True,
        "priority": 5,
    }
    start = time.monotonic()
    try:
        resp = await client.post(f"{queue_url}/enqueue", json=payload)
        if resp.status_code != 200:
            stats.errors += 1
            return

        task_id = resp.json()["task_id"]

        # Poll for result (max 120s)
        for _ in range(240):
            await asyncio.sleep(0.5)
            status_resp = await client.get(f"{queue_url}/status/{task_id}")
            if status_resp.status_code != 200:
                continue
            status = status_resp.json()
            if status["status"] == "completed":
                latency_ms = (time.monotonic() - start) * 1000
                stats.success += 1
                stats.latencies.append(latency_ms)
                if status.get("result", {}).get("cached"):
                    stats.cache_hits += 1
                return
            elif status["status"] == "failed":
                stats.errors += 1
                return

        stats.errors += 1  # timeout

    except Exception:
        stats.errors += 1


async def run_load_test(gateway_url: str, queue_url: str, num_users: int, rounds: int):
    print(f"\n{'='*60}")
    print(f"  Fazle Load Test — {num_users} concurrent users, {rounds} rounds")
    print(f"  Gateway: {gateway_url}")
    print(f"  Queue:   {queue_url}")
    print(f"{'='*60}\n")

    # ── Test 1: Gateway Health ──
    print("Checking service health...")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.get(f"{gateway_url}/health")
            print(f"  Gateway: {r.json().get('status', 'unknown')}")
        except Exception as e:
            print(f"  Gateway: UNREACHABLE ({e})")

        try:
            r = await client.get(f"{queue_url}/health")
            print(f"  Queue:   {r.json().get('status', 'unknown')}")
        except Exception as e:
            print(f"  Queue:   UNREACHABLE ({e})")

    print()

    # ── Test 2: Synchronous Gateway Load ──
    print(f"[Phase 1] Synchronous gateway — {num_users} users × {rounds} rounds")
    sync_stats = Stats()
    async with httpx.AsyncClient(timeout=180.0) as client:
        for round_num in range(rounds):
            tasks = []
            for user_id in range(num_users):
                tasks.append(test_gateway_sync(client, gateway_url, user_id, round_num * num_users + user_id, sync_stats))
            await asyncio.gather(*tasks)
            print(f"  Round {round_num + 1}/{rounds} complete — {sync_stats.success} ok, {sync_stats.errors} err, {sync_stats.rate_limited} limited")

    print(sync_stats.summary("Sync Gateway"))
    print()

    # ── Test 3: Async Queue Load ──
    print(f"[Phase 2] Async queue — {num_users} users × {rounds} rounds")
    queue_stats = Stats()
    async with httpx.AsyncClient(timeout=180.0) as client:
        for round_num in range(rounds):
            tasks = []
            for user_id in range(num_users):
                tasks.append(test_queue_async(client, queue_url, user_id, round_num * num_users + user_id, queue_stats))
            await asyncio.gather(*tasks)
            print(f"  Round {round_num + 1}/{rounds} complete — {queue_stats.success} ok, {queue_stats.errors} err")

    print(queue_stats.summary("Async Queue"))
    print()

    # ── Test 4: Rate Limit Test ──
    print("[Phase 3] Rate limit burst — 30 requests from same user in 1s")
    rate_stats = Stats()
    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = []
        for i in range(30):
            tasks.append(test_gateway_sync(client, gateway_url, 9999, i, rate_stats))
        await asyncio.gather(*tasks)
    print(rate_stats.summary("Rate Limit Burst"))
    print()

    # ── Test 5: Cache Effectiveness ──
    print("[Phase 4] Cache test — same prompt 20 times")
    cache_stats = Stats()
    async with httpx.AsyncClient(timeout=30.0) as client:
        for i in range(20):
            await test_gateway_sync(client, gateway_url, 8888, 0, cache_stats)
    print(cache_stats.summary("Cache Test"))
    print()

    # ── Queue Info ──
    print("[Queue Status]")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.get(f"{queue_url}/queue/info")
            info = r.json()
            print(f"  Stream length: {info.get('length', 'N/A')}")
            for g in info.get("groups", []):
                print(f"  Group '{g['name']}': {g.get('consumers', 0)} consumers, {g.get('pending', 0)} pending")
        except Exception as e:
            print(f"  Could not fetch queue info: {e}")

    print(f"\n{'='*60}")
    print("  Load test complete")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Fazle Load Test")
    parser.add_argument("--gateway", default="http://localhost:8800", help="LLM Gateway URL")
    parser.add_argument("--queue", default="http://localhost:8810", help="Queue service URL")
    parser.add_argument("--users", type=int, default=50, help="Number of concurrent users")
    parser.add_argument("--rounds", type=int, default=3, help="Number of test rounds")
    args = parser.parse_args()
    asyncio.run(run_load_test(args.gateway, args.queue, args.users, args.rounds))


if __name__ == "__main__":
    main()
